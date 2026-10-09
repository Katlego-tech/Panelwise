"""The frame audit: describe blind, judge against the shot, check in code. docs/design/verify.md §4.

New in Panelwise: FrameFlow had no image audit. What the judge says is only trusted as far as
code can check it; "supported by the script" needs a verbatim quote, found the way the grounding
filter finds one (verify.md §8). A failed call is an ERROR audit, never a pass.
"""

import base64
import hashlib
import logging
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
}
# Things a location never "naturally holds": each is a story choice the script must make.
_NEVER_DRESSING = frozenset(
    {
        ObjectCategory.ANIMAL,
        ObjectCategory.VEHICLE,
        ObjectCategory.WEAPON,
        ObjectCategory.SCREEN_OR_SIGN,
        ObjectCategory.FOOD,
    }
)
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


def _calls_each_once(indexes: Sequence[int], n: int) -> bool:
    return sorted(indexes) == list(range(n))


def run_checks(
    shot: Shot,
    scene: Scene,
    description: FrameDescription,
    judgement: Judgement,
    extraction: Extraction,
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

    for call in sorted(judgement.objects, key=lambda c: c.object):
        obj = description.objects[call.object]
        what = f"object {call.object} ({obj.name}, {obj.category})"
        match call.kind:
            case ObjectKind.UNSCRIPTED:
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: unscripted")
            case ObjectKind.SCRIPTED_PROP if not _found(call.support, supports):
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: prop without support")
            case ObjectKind.SET_DRESSING if obj.held:
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: held, so not set dressing")
            case ObjectKind.SET_DRESSING if obj.category in _NEVER_DRESSING:
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: never set dressing")
            case ObjectKind.SET_DRESSING if not _found(call.support, heading):
                failures[Check.UNSCRIPTED_OBJECT].append(f"{what}: not in the heading")
            case _:
                pass

    if description.has_text:
        failures[Check.TEXT_IN_FRAME].append("text in the frame")

    contradicts = {IntExt.INT: Setting.EXTERIOR, IntExt.EXT: Setting.INTERIOR}
    if contradicts.get(scene.int_ext) == description.setting:
        failures[Check.SETTING].append(f"{description.setting} in a {scene.int_ext} scene")

    failures[Check.MISSING_CHARACTER] += [
        f"{name} not seen" for name in people if name not in positions
    ]

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
    extraction: Extraction,
    description: FrameDescription,
) -> tuple[Judgement, ChatResult]:
    messages = [
        {"role": "system", "content": JUDGE_PROMPT},
        {"role": "user", "content": render_spec(shot, scene, extraction, description)},
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
        judgement, chat = await _judge(model, shot, scene, extraction, description)
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
        checks, verdict, positions = run_checks(shot, scene, description, judgement, extraction)

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
