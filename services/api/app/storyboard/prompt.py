"""The frame prompt: Non-negotiable I on the input to the image model. docs/design/storyboard.md
§3.1.

A pure function of the shot, the screenplay, the extraction and the style. Its script words come
only from this shot's scene heading and the Action elements it covers, each part tagged with the
span it came from, so a test (and a reader) can check every word against the script. It takes no
free text: not the shot's rationale, not a model's description, not a character's introduction
from another shot (it would carry that moment's event into this frame). Dialogue, parentheticals
and camera movement never enter it: speech isn't visible and puts letters in the art, and a still
can't pan. Names are redacted before anything else happens to the text.

Ported from FrameFlow's storyboard_service.py: comma phrases (how CLIP reads captions), the medium
first, the setting as "inside <place>" straight after the framing, the resolved clock, the framing
vocabulary. Not ported: the free-text frame description and its fallback to the scene's first 400
characters of action, the movement words, and the `classic` prompt's negations.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from app.characters import name_tokens, redact
from app.characters.labels import animals, redaction_labels
from app.grounding import Extraction
from app.script import (
    Action,
    Dialogue,
    IntExt,
    Scene,
    Screenplay,
    Span,
    absolute_time,
    match_speaker,
)
from app.shots import Framing, Shot
from app.storyboard.styles import Style


class PartKind(StrEnum):
    STYLE = "style"
    FRAMING = "framing"
    SETTING = "setting"
    TIME = "time"
    COUNT = "count"
    AGE = "age"  # T074: a visible character's age, from the script's introduction
    LOOK = "look"  # T079: their description, verbatim from that introduction
    PLACEMENT = "placement"
    ACTION = "action"


@dataclass(frozen=True)
class PromptPart:
    kind: PartKind
    text: str
    span: Span | None  # where a script part came from; None for the style's and code's words


@dataclass(frozen=True)
class FramePrompt:
    parts: tuple[PromptPart, ...]
    trimmed: int  # ACTION parts dropped or cut to fit the word budget

    def text(self) -> str:
        return ", ".join(p.text for p in self.parts)


class PromptError(ValueError):
    """The fixed parts alone exceed the word budget: a style or location too long for the encoder
    is a configuration error, never a silently truncated prompt."""


FRAMING_WORDS: Mapping[Framing, str] = MappingProxyType(
    {
        Framing.WIDE: "wide shot",
        Framing.MEDIUM: "medium shot",
        Framing.CLOSE_UP: "close-up",
        Framing.EXTREME_CLOSE_UP: "extreme close-up",
        Framing.OVER_SHOULDER: "over-the-shoulder shot",
        Framing.POV: "point-of-view shot",
        Framing.INSERT: "close-up insert shot",
    }
)
PLACEMENT_PHRASES: frozenset[str] = frozenset({"one figure on the left, one on the right"})
OFF_SCREEN_MARKS: tuple[str, ...] = ("V.O.", "O.S.", "O.C.", "OFF")

_PREPOSITIONS: Mapping[IntExt, str] = MappingProxyType(
    {IntExt.INT: "inside", IntExt.EXT: "outside", IntExt.INT_EXT: "at"}
)
_COUNTS: Mapping[int, str] = MappingProxyType(
    {1: "one figure", 2: "two figures", 3: "three figures", 4: "four figures"}
)
_GROUP = "a group of figures"
_CLOSERS = "\"')]\u201d\u2019"


def heading_span(scene: Scene) -> Span:
    """The heading line alone: `Scene.span` runs on to the scene's last element."""
    return Span(scene.span.page, scene.span.line_start, scene.span.line_start)


def time_source(scenes: Sequence[Scene], scene_index: int) -> int | None:
    """The scene whose own heading supplied `resolve_times`' clock for this one: itself, else the
    nearest earlier scene with an absolute time, else None. A CONTINUOUS scene's night cites the
    heading that says NIGHT."""
    for i in range(scene_index, -1, -1):
        if absolute_time(scenes[i].time_of_day) is not None:
            return i
    return None


def visible_characters(
    shot: Shot, screenplay: Screenplay, extraction: Extraction
) -> tuple[str, ...]:
    """The planner's characters that the covered elements put on screen, in the planner's order:
    an on-screen speaker (not V.O., O.S., O.C. or OFF), or a character an action line names by
    its name or a paired other name. People only: an animal is never a figure (T052)."""
    scene = screenplay.scenes[shot.scene_index]
    beings = animals(extraction)
    own = {c: _own_labels(c, screenplay, extraction) for c in shot.characters}
    shown: set[str] = set()
    heard: set[str] = set()  # T079: planner characters who speak off screen here
    off_screen = False  # T079: any covered line spoken off screen, by anyone
    for i in shot.elements:
        element = scene.elements[i]
        if isinstance(element, Dialogue):
            extension = (element.extension or "").upper()
            if any(mark in extension for mark in OFF_SCREEN_MARKS):
                off_screen = True
                if (who := match_speaker(element.cue, shot.characters)) is not None:
                    heard.add(who)
                continue
            if (who := match_speaker(element.cue, shot.characters)) is not None:
                shown.add(who)
        else:
            # Named in the line exactly when redacting that one character changes it.
            shown.update(c for c in shot.characters if redact(element.text, own[c]) != element.text)
    people = tuple(c for c in shot.characters if c in shown and c not in beings)
    if people or not off_screen:
        return people
    # T079: a line heard off screen and no one on screen: the planner's others are listening.
    return tuple(c for c in shot.characters if c not in heard and c not in beings)


# A character introduced the way screenplays do: `NAME (` and an age in years (T074). A number, an
# optional `s`, an optional years word, then , ; or ): `(5 months)` is no age.
def _introduction(character: str, screenplay: Screenplay) -> tuple[Action, re.Match[str]] | None:
    pattern = re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(character)}\s*\(\s*(\d{{1,3}})(s?)"
        rf"\s*(?:years?[- ]old|yrs?|yo|y/o)?\s*[,;)]"
    )
    for scene in screenplay.scenes:
        for element in scene.elements:
            if isinstance(element, Action) and (m := pattern.search(element.text)):
                return element, m
    return None


def _other_names(character: str, screenplay: Screenplay) -> frozenset[str]:
    """Other characters' name words, lower case (T079 review): every dialogue cue and every
    `NAME (` introduction, less `character`'s own words and titles. Props in capitals (RED KITE)
    are neither, so they bound nothing."""
    names: set[str] = set()
    for scene in screenplay.scenes:
        for element in scene.elements:
            if isinstance(element, Dialogue):
                names.add(element.cue)
            else:
                names.update(m.group(1) for m in _INTRODUCED.finditer(element.text))
    own = set(character.lower().split())
    words = {w for n in names for w in re.findall(r"[a-z]+", n.lower())}
    return frozenset(w for w in words - own - _TITLES if len(w) > 1)


_INTRODUCED = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z'. -]*[A-Z])\s*\(\s*\d")
_TITLES = frozenset({"mr", "mrs", "ms", "dr", "officer", "mama", "papa", "the"})
_NOT_A_LOOK = re.compile(r"[(\d]|^(?:and|who|then|as|while|but)\b", re.IGNORECASE)
_NEXT_INTRODUCTION = re.compile(r"(?<![A-Za-z0-9])[A-Z][A-Z'. -]*[A-Z]\s*\(")
_LOOK_MAX_WORDS = 8
_ACTION_FLOOR = 12  # words a shot's action keeps before any look (T079)


def _look_of(element: Action, m: re.Match[str], name: str, screenplay: Screenplay) -> str | None:
    """§3.1's LOOK, read from an introduction's match: the parenthesis's items after the age, then
    the comma phrase right after it when a comma closes that phrase before the sentence ends."""
    text = element.text
    close = text.find(")", m.end() - 1)
    # No closing parenthesis in the introducing sentence: nothing here is surely a look.
    if close < 0 or re.search(r"[.!?]", text[m.end() - 1 : close]):
        return None
    items = [i.strip() for i in re.split(r"[,;]", text[m.end() - 1 : close].lstrip(",;)"))]
    after = re.match(r"\s*,\s*([^,.;!?]+),", text[close + 1 :])
    if after:
        items.append(after.group(1).strip())
    others = _other_names(name, screenplay)
    kept = [
        " ".join(i.split())
        for i in items
        if i
        and len(i.split()) <= _LOOK_MAX_WORDS
        and not _NOT_A_LOOK.search(i)  # a conjunction, a parenthesis or a number: not a look
        and not others & set(re.findall(r"[a-z]+", i.lower()))  # nor someone else's
    ]
    return ", ".join(kept) or None


def introduced_look(character: str, screenplay: Screenplay) -> tuple[str, Span] | None:
    """The description the introduction gives (T079), verbatim: `LERATO (10), braids tied back,
    grips…` -> "braids tied back"; `NANDI (60s, oilskin coat)` -> "oilskin coat"; with the
    introducing element's span. Its action (`grips a RED KITE`) is that moment's event: left out."""
    found = _introduction(character, screenplay)
    if found is None:
        return None
    look = _look_of(*found, character, screenplay)
    return (look, found[0].span) if look else None


def introduced_sex(character: str, screenplay: Screenplay) -> Literal["female", "male"] | None:
    """The sex the introduction's own pronouns give (T079): "she"/"he" in the introducing sentence
    (to its end or the next introduction), "her"/"his" inside its look. One sex only, else None:
    `MAMA THEMBI (60s), the shop's owner, watches her` is someone else's "her"; a later sentence's
    "She waves" may be anyone."""
    found = _introduction(character, screenplay)
    if found is None:
        return None
    element, m = found
    rest = element.text[m.end() :]
    if nxt := _NEXT_INTRODUCTION.search(rest):
        rest = rest[: nxt.start()]
    # T079 review: a "he" after another character's name may be theirs ("watches SIPHO as he").
    others = _other_names(character, screenplay)
    if hit := next(
        (w for w in re.finditer(r"[A-Za-z]+", rest) if w.group().lower() in others), None
    ):
        rest = rest[: hit.start()]
    if end := re.search(r"[.!?](?:\s|$)", rest):
        rest = rest[: end.start()]
    words = set(re.findall(r"[a-z]+", rest.lower()) if rest else [])
    look = set(re.findall(r"[a-z]+", (_look_of(element, m, character, screenplay) or "").lower()))
    female = "she" in words or "her" in look
    male = "he" in words or "his" in look
    if female == male:
        return None
    return "female" if female else "male"


def introduced_age(character: str, screenplay: Screenplay) -> tuple[str, Span] | None:
    """The age the script gives where an Action line introduces `character` (T074): `LERATO (10)`
    -> "a 10-year-old", `MOKGOSI (70s)` -> "a person in their 70s", with that element's span; T079:
    with the sex `introduced_sex` reads, "a 10-year-old girl", "a man in his 70s". Only the
    parenthesis's own number and the code's fixed sex words."""
    found = _introduction(character, screenplay)
    if found is None:
        return None
    element, m = found
    number, decade = int(m.group(1)), m.group(2)
    sex = introduced_sex(character, screenplay)
    young = number < 18
    noun = {
        "female": "girl" if young else "woman",
        "male": "boy" if young else "man",
    }.get(sex or "")
    if decade:
        own = {"female": "her", "male": "his"}.get(sex or "", "their")
        age = f"a {noun or 'person'} in {own} {number}s"
    else:
        age = f"a {number}-year-old" + (f" {noun}" if noun else "")
    return age, element.span


def _own_labels(character: str, screenplay: Screenplay, extraction: Extraction) -> dict[str, str]:
    """One character's labels; a planner name the extraction lacks still redacts as a name."""
    return redaction_labels(extraction, screenplay, only=character) or {
        token: "a person" for token in name_tokens([character])
    }


def build_frame_prompt(
    shot: Shot,
    screenplay: Screenplay,
    extraction: Extraction,
    style: Style,
    *,
    max_words: int,
    placement: str | None = None,
) -> FramePrompt:
    scene = screenplay.scenes[shot.scene_index]
    labels = redaction_labels(extraction, screenplay)
    visible = visible_characters(shot, screenplay, extraction)
    where = f"shot {shot.number} of scene {scene.number or scene.index + 1}"

    def script(text: str) -> str:
        # Redacted first, before any lower-casing: names are found by their capitals.
        return " ".join(redact(text, labels).split())

    parts = [
        PromptPart(
            PartKind.STYLE,
            f"{style.medium}, {style.finish}" if style.finish else style.medium,
            None,
        ),
        PromptPart(PartKind.FRAMING, FRAMING_WORDS[shot.framing], None),
    ]
    if location := script(scene.location).lower():
        parts.append(
            PromptPart(
                PartKind.SETTING, f"{_PREPOSITIONS[scene.int_ext]} {location}", heading_span(scene)
            )
        )
    if shot.time_of_day is not None:
        source = time_source(screenplay.scenes, scene.index)
        clock = absolute_time(screenplay.scenes[source].time_of_day) if source is not None else None
        # The planner copies resolve_times' clock; any other value is not what the headings say.
        if source is None or clock is None or clock != shot.time_of_day.strip().upper():
            raise ValueError(
                f"{where}: time of day {shot.time_of_day!r} is not the clock its headings give "
                f"({clock!r})"
            )
        parts.append(
            PromptPart(
                # Not redacted: `absolute_time` already limits it to ABSOLUTE_TIMES, and a
                # character named DAWN must not turn the clock into "a person" (PR #27 review).
                PartKind.TIME,
                clock.lower(),
                heading_span(screenplay.scenes[source]),
            )
        )
    covered = {scene.elements[i].span for i in shot.elements}
    if visible:
        parts.append(PromptPart(PartKind.COUNT, _COUNTS.get(len(visible), _GROUP), None))
        for character in visible:  # T074, T079: each one's age, then look, as the script gives them
            if (age := introduced_age(character, screenplay)) is not None:
                parts.append(PromptPart(PartKind.AGE, age[0], age[1]))
            # Not when the shot covers that line: its ACTION part already says it, word for word.
            look = introduced_look(character, screenplay)
            if look is not None and look[1] not in covered:
                parts.append(PromptPart(PartKind.LOOK, script(look[0]), look[1]))
    if placement is not None:
        if placement not in PLACEMENT_PHRASES:
            raise ValueError(f"{where}: unknown placement {placement!r}")
        if len(visible) != 2:
            raise ValueError(
                f"{where}: a placement needs exactly two figures on screen, not {len(visible)}"
            )
        parts.append(PromptPart(PartKind.PLACEMENT, placement, None))

    fixed = _words([p for p in parts if p.kind is not PartKind.LOOK])
    if fixed > max_words:
        raise PromptError(
            f"{where}: the style, framing, setting, time and figure words alone are {fixed} "
            f"words, over the budget of {max_words}"
        )

    actions = [
        PromptPart(PartKind.ACTION, text, element.span)
        for i in sorted(shot.elements)
        if isinstance(element := scene.elements[i], Action) and (text := script(element.text))
    ]
    # T079: looks give way to the budget, from the last character back, so the shot's action
    # keeps at least _ACTION_FLOOR words; a look never fails a render.
    while (k := [i for i, p in enumerate(parts) if p.kind is PartKind.LOOK]) and (
        _words(parts) > max_words - _ACTION_FLOOR
    ):
        del parts[k[-1]]
    actions, trimmed = _fit(actions, max_words - _words(parts))
    return FramePrompt(tuple(parts + actions), trimmed)


def _words(parts: Sequence[PromptPart]) -> int:
    # ", " joins parts without adding a word, so a prompt's words are its parts' words.
    return sum(len(p.text.split()) for p in parts)


def _fit(actions: list[PromptPart], budget: int) -> tuple[list[PromptPart], int]:
    """Drop whole parts from the tail, never the first; then cut the first to its longest prefix
    that fits, ending at a sentence end if one fits, else at a word; drop it if no word fits.
    Only script words are removed: what is kept is a verbatim prefix."""
    trimmed = 0
    while len(actions) > 1 and _words(actions) > budget:
        actions.pop()
        trimmed += 1
    if not actions or _words(actions) <= budget:
        return actions, trimmed
    words = actions[0].text.split()[: max(budget, 0)]
    ends = [
        k
        for k in range(len(words), 0, -1)
        if words[k - 1].rstrip(_CLOSERS).endswith((".", "!", "?"))
    ]
    cut = " ".join(words[: ends[0]] if ends else words)
    return ([replace(actions[0], text=cut)] if cut else []), trimmed + 1
