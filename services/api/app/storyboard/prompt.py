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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType

from app.characters import redact_all
from app.grounding import EntityKind, Extraction
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


def visible_characters(shot: Shot, scene: Scene) -> tuple[str, ...]:
    """The planner's characters that the covered elements put on screen, in the planner's order:
    an on-screen speaker (not V.O., O.S., O.C. or OFF), or a character an action line names."""
    shown: set[str] = set()
    for i in shot.elements:
        element = scene.elements[i]
        if isinstance(element, Dialogue):
            extension = (element.extension or "").upper()
            if any(mark in extension for mark in OFF_SCREEN_MARKS):
                continue
            if (who := match_speaker(element.cue, shot.characters)) is not None:
                shown.add(who)
        else:
            # Named in the line exactly when redacting that one name changes it.
            shown.update(
                c for c in shot.characters if redact_all(element.text, [c]) != element.text
            )
    return tuple(c for c in shot.characters if c in shown)


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
    names = [e.name for e in extraction.entities if e.kind is EntityKind.CHARACTER]
    visible = visible_characters(shot, scene)
    where = f"shot {shot.number} of scene {scene.number or scene.index + 1}"

    def script(text: str) -> str:
        # Redacted first, before any lower-casing: names are found by their capitals.
        return " ".join(redact_all(text, names).split())

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
    if visible:
        parts.append(PromptPart(PartKind.COUNT, _COUNTS.get(len(visible), _GROUP), None))
    if placement is not None:
        if placement not in PLACEMENT_PHRASES:
            raise ValueError(f"{where}: unknown placement {placement!r}")
        if len(visible) != 2:
            raise ValueError(
                f"{where}: a placement needs exactly two figures on screen, not {len(visible)}"
            )
        parts.append(PromptPart(PartKind.PLACEMENT, placement, None))

    fixed = _words(parts)
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
    actions, trimmed = _fit(actions, max_words - fixed)
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
