"""The frame audit: describe blind, judge against the shot, check in code. docs/design/verify.md §4.

New in Panelwise: FrameFlow had no image audit. What the judge says is only trusted as far as
code can check it; "supported by the script" needs a verbatim quote, found the way the grounding
filter finds one (verify.md §8). A failed call is an ERROR audit, never a pass.
"""

import base64
import hashlib
import logging
import re
from collections.abc import Sequence

from pydantic import ValidationError

from app.characters.labels import animals
from app.grounding import EntityKind, Extraction, normalize_for_grounding
from app.llm import ChatResult, LLMError, NebiusChatModel, Tier, Usage, structured_chat
from app.script import IntExt, Scene, Screenplay, match_speaker
from app.shots import Framing, Shot
from app.verify.model import (
    Audit,
    Check,
    CheckResult,
    Light,
    ObjectCategory,
    ObjectKind,
    Position,
    RenderedFrame,
    Setting,
    Severity,
    ShotSize,
    Verdict,
)
from app.verify.prompts import DESCRIBE_PROMPT, JUDGE_PROMPT, render_spec
from app.verify.schema import FrameDescription, Judgement

logger = logging.getLogger(__name__)

_SEVERITY = {
    Check.UNSCRIPTED_PERSON: Severity.HARD,
    Check.UNSCRIPTED_OBJECT: Severity.HARD,
    Check.TEXT_IN_FRAME: Severity.HARD,
    Check.SETTING: Severity.HARD,
    Check.MISSING_CHARACTER: Severity.SOFT,
    Check.LIGHT: Severity.SOFT,
    Check.FRAMING: Severity.SOFT,
    # An artist's mark is no character, prop, line or event: shown, never withheld (T077).
    Check.SIGNATURE: Severity.SOFT,
    # None of the people the prompt drew is in the frame: it isn't this shot (T080).
    Check.NO_CHARACTER: Severity.HARD,
}
# Things a location never "naturally holds": each is a story choice the script must make.
# A sign may be dressing (T071): its words are what could be unscripted, and TEXT_IN_FRAME
# checks them.
_NEVER_DRESSING = frozenset(
    {
        ObjectCategory.ANIMAL,
        ObjectCategory.VEHICLE,
        ObjectCategory.WEAPON,
        ObjectCategory.FOOD,
    }
)
# Costume and the place's own structure: never a story choice when nobody holds it (T071).
_NEVER_UNSCRIPTED = frozenset({ObjectCategory.CLOTHING, ObjectCategory.ARCHITECTURE})
_NIGHT_TIMES = frozenset({"NIGHT", "MIDNIGHT", "EVENING"})
_DAY_TIMES = frozenset({"DAY", "MORNING", "AFTERNOON"})
_FRAMING_STEP = {
    Framing.WIDE: 0,
    Framing.MEDIUM: 1,
    Framing.OVER_SHOULDER: 1,
    Framing.POV: 1,
    Framing.CLOSE_UP: 2,
    Framing.INSERT: 2,
    Framing.EXTREME_CLOSE_UP: 3,
}
_SIZE_STEP = {ShotSize.WIDE: 0, ShotSize.MEDIUM: 1, ShotSize.CLOSE: 2, ShotSize.EXTREME_CLOSE: 3}


def seed_for(shot: Shot, attempt: int) -> int:
    key = f"{shot.scene_index}:{shot.number}:{attempt}".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big")


def _found(support: str | None, haystacks: Sequence[str]) -> bool:
    needle = normalize_for_grounding(support or "")
    return bool(needle) and any(needle in h for h in haystacks)


def _in_words(needle: str, haystacks: Sequence[str]) -> bool:
    """`needle`, normalised, appears in a haystack as whole words (T071): a stray letter inside
    another word isn't the script's."""
    words = normalize_for_grounding(needle)
    pattern = re.compile(rf"(?<!\w){re.escape(words)}(?!\w)")
    return bool(words) and any(pattern.search(h) for h in haystacks)


def _names_any(support: str | None, names: Sequence[str]) -> bool:
    """The support names one of `names` (T072): a quote about a character excuses no stranger."""
    return any(_in_words(name, [normalize_for_grounding(support or "")]) for name in names)


def _named_prop(name: str, props: Sequence[frozenset[str]]) -> bool:
    """Every word of `name` is a word of one prop the extraction names (T072): `kite` against
    `RED KITE`. Such a thing is a story choice, never set dressing."""
    words = frozenset(normalize_for_grounding(name).split())
    return bool(words) and any(words <= prop for prop in props)


# Words that make a thing another copy of a prop rather than a part of it (T078).
_COPY_WORDS = frozenset(
    {"second", "another", "other", "extra", "spare", "two", "three", "more", "duplicate"}
)


def part_of_prop(
    name: str, category: ObjectCategory, shot: Shot, extraction: Extraction
) -> str | None:
    """The shot prop whose part `name` is (T078): the prop's head noun (its name's last word) is
    the name's second-to-last word, with no copy word, and never an animal, vehicle, weapon or
    food. `kite string` is part of `RED KITE`; `kite`, `blue kite`, `second kite` and
    `map of the town` are judged as before."""
    words = normalize_for_grounding(name).lower().split()
    if len(words) < 2 or _COPY_WORDS & set(words) or category in _NEVER_DRESSING:
        return None
    for prop in shot.props:
        quoted = any(
            e.kind is EntityKind.PROP and e.name == prop and e.quotes for e in extraction.entities
        )
        if quoted and normalize_for_grounding(prop).lower().split()[-1:] == words[-2:-1]:
            return prop
    return None


def _calls_each_once(indexes: Sequence[int], n: int) -> bool:
    return sorted(indexes) == list(range(n))


def run_checks(
    shot: Shot,
    scene: Scene,
    description: FrameDescription,
    judgement: Judgement,
    extraction: Extraction,
    *,
    on_screen: tuple[str, ...] = (),
) -> tuple[tuple[CheckResult, ...], Verdict, dict[str, Position]]:
    if not (
        _calls_each_once([c.person for c in judgement.people], len(description.people))
        and _calls_each_once([c.object for c in judgement.objects], len(description.objects))
    ):
        return (), Verdict.ERROR, {}

    # An animal character is described as an object: people are matched to people only (T052).
    beings = animals(extraction)
    people = tuple(c for c in shot.characters if c not in beings)
    in_shot = {(EntityKind.CHARACTER, n) for n in shot.characters} | {
        (EntityKind.PROP, n) for n in shot.props
    }
    supports = [normalize_for_grounding(shot.source)] + [
        normalize_for_grounding(q.text)
        for e in extraction.entities
        if (e.kind, e.name) in in_shot
        for q in e.quotes
    ]
    heading = [normalize_for_grounding(scene.heading)]
    props = [
        frozenset(normalize_for_grounding(e.name).split())
        for e in extraction.entities
        if e.kind is EntityKind.PROP
    ]
    failures: dict[Check, list[str]] = {check: [] for check in Check}

    positions: dict[str, Position] = {}
    for call in sorted(judgement.people, key=lambda c: c.person):
        person = description.people[call.person]
        who = f"person {call.person} ({person.position}, {person.appearance})"
        name = match_speaker(call.character, people) if call.character else None
        if name is not None and name in positions:
            failures[Check.UNSCRIPTED_PERSON].append(f"{who}: {name} is already another person")
        elif name is not None:
            positions[name] = person.position
        elif not _found(call.support, supports):
            failures[Check.UNSCRIPTED_PERSON].append(f"{who}: no shot character, no support")
        elif _names_any(call.support, people):
            failures[Check.UNSCRIPTED_PERSON].append(f"{who}: its support is about a character")

    for call in sorted(judgement.objects, key=lambda c: c.object):
        obj = description.objects[call.object]
        what = f"object {call.object} ({obj.name}, {obj.category})"
        if obj.category in _NEVER_UNSCRIPTED and not obj.held:
            continue
        if part_of_prop(obj.name, obj.category, shot, extraction):
            continue  # T078: whatever the judge said; its support is the prop's quote
        match call.kind:
            case ObjectKind.UNSCRIPTED:
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: unscripted")
            case ObjectKind.SCRIPTED_PROP if not _found(call.support, supports):
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: prop without support")
            case ObjectKind.SET_DRESSING if obj.held:
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: held, so not set dressing")
            case ObjectKind.SET_DRESSING if _named_prop(obj.name, props):
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: the script names it")
            case ObjectKind.SET_DRESSING if obj.category in _NEVER_DRESSING:
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: never set dressing")
            case ObjectKind.SET_DRESSING if not _found(call.support, heading):
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: not in the heading")
            case _:
                pass

    # Only legible words the script never wrote (T071): the shot's own text or the scene's place.
    # The heading's time of day isn't a haystack, so a painted "NIGHT" fails.
    words = [normalize_for_grounding(shot.source), normalize_for_grounding(scene.location)]
    if description.signature:  # T077: soft; any words read in it are still `text`, below
        failures[Check.SIGNATURE].append("a signature or artist's mark")
    failures[Check.TEXT_IN_FRAME] += [
        f"text {t!r} isn't the script's"
        for t in description.text
        if normalize_for_grounding(t) and not _in_words(t, words)  # "" is no text read
    ]

    contradicts = {IntExt.INT: Setting.EXTERIOR, IntExt.EXT: Setting.INTERIOR}
    if contradicts.get(scene.int_ext) == description.setting:
        failures[Check.SETTING].append(f"{description.setting} in a {scene.int_ext} scene")

    failures[Check.MISSING_CHARACTER] += [
        f"{name} not seen" for name in people if name not in positions
    ]
    if on_screen and not any(name in positions for name in on_screen):  # T080
        failures[Check.NO_CHARACTER].append(f"none of {', '.join(on_screen)} in frame")

    time = (shot.time_of_day or "").upper()
    if (description.light is Light.DAY and time in _NIGHT_TIMES) or (
        description.light is Light.NIGHT and time in _DAY_TIMES
    ):
        failures[Check.LIGHT].append(f"{description.light} light at {time}")

    size = _SIZE_STEP.get(description.shot_size)
    if size is not None and abs(size - _FRAMING_STEP[shot.framing]) >= 2:
        failures[Check.FRAMING].append(f"{description.shot_size} for a {shot.framing} shot")

    checks = tuple(
        CheckResult(check, _SEVERITY[check], not failed, "; ".join(failed))
        for check, failed in failures.items()
    )
    if any(not c.ok and c.severity is Severity.HARD for c in checks):
        verdict = Verdict.FAIL
    elif any(not c.ok for c in checks):
        verdict = Verdict.WARN
    else:
        verdict = Verdict.PASS
    return checks, verdict, positions


async def describe_frame(model: NebiusChatModel, png: bytes) -> tuple[FrameDescription, ChatResult]:
    image = f"data:image/png;base64,{base64.b64encode(png).decode()}"
    messages = [
        {"role": "system", "content": DESCRIBE_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {"type": "image_url", "image_url": {"url": image}},
            ],
        },
    ]
    result = await structured_chat(model, messages, FrameDescription, Tier.VISION, max_tokens=4096)
    return result.value, result.chat


async def _judge(
    model: NebiusChatModel,
    shot: Shot,
    scene: Scene,
    screenplay: Screenplay,
    extraction: Extraction,
    description: FrameDescription,
) -> tuple[Judgement, ChatResult]:
    messages = [
        {"role": "system", "content": JUDGE_PROMPT},
        {"role": "user", "content": render_spec(shot, scene, screenplay, extraction, description)},
    ]
    result = await structured_chat(model, messages, Judgement, Tier.REASONING, max_tokens=16384)
    return result.value, result.chat


async def audit_frame(
    model: NebiusChatModel,
    frame: RenderedFrame,
    shot: Shot,
    screenplay: Screenplay,
    extraction: Extraction,
) -> Audit:
    scene = screenplay.scenes[shot.scene_index]
    chats: list[ChatResult] = []
    description: FrameDescription | None = None
    judgement: Judgement | None = None
    step = "describe"
    try:
        description, chat = await describe_frame(model, frame.png)
        chats.append(chat)
        step = "judge"
        judgement, chat = await _judge(model, shot, scene, screenplay, extraction, description)
        chats.append(chat)
    except (LLMError, ValidationError) as exc:
        # Which step failed, and an LLMError's message: it names the model, status and finish
        # reason, never the request (llm.md §4). A ValidationError's type only: it quotes the
        # output, which can quote the script.
        detail = str(exc) if isinstance(exc, LLMError) else type(exc).__name__
        logger.warning(
            "audit of shot %s attempt %d failed at %s: %s",
            frame.shot,
            frame.attempt,
            step,
            detail,
        )
        checks: tuple[CheckResult, ...] = ()
        verdict, positions = Verdict.ERROR, {}
    else:
        # T080: against the people the prompt drew. Imported here: T026's renderer modules in
        # app.storyboard import app.verify, so a module-level import would be a cycle there.
        from app.storyboard.prompt import visible_characters

        on_screen = visible_characters(shot, screenplay, extraction)
        checks, verdict, positions = run_checks(
            shot, scene, description, judgement, extraction, on_screen=on_screen
        )

    return Audit(
        shot=frame.shot,
        attempt=frame.attempt,
        seed=frame.seed,
        description=description,
        judgement=judgement,
        checks=checks,
        verdict=verdict,
        positions=positions,
        models=tuple(dict.fromkeys(c.model for c in chats)),
        usage=Usage(
            prompt_tokens=sum(c.usage.prompt_tokens for c in chats),
            completion_tokens=sum(c.usage.completion_tokens for c in chats),
            reasoning_tokens=sum(c.usage.reasoning_tokens for c in chats),
        ),
    )
