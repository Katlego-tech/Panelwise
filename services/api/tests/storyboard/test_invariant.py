"""Non-negotiable I on the input to the image model: storyboard.md §3.1's invariant, §9.

Over every self-written sample in samples/, every shot a planner could make (every consecutive
run of elements in every scene: a superset of any real plan), every public style, and two word
budgets (the default and one that trims nothing): every script part of the prompt cites this
shot's heading, the heading its clock came from, or an element the shot covers, and says only
what that redacted line says. No name, no dialogue, no parenthetical, no rationale.
"""

import re
from collections.abc import Iterator
from functools import cache
from itertools import cycle, pairwise

import pytest

from app.characters import name_tokens, redact_all
from app.grounding import EntityKind, Extraction, normalize_for_grounding
from app.script import ABSOLUTE_TIMES, Action, Dialogue, Screenplay, Span, parse_pdf, resolve_times
from app.shots import Framing, Shot
from app.storyboard import (
    FRAMING_WORDS,
    PUBLIC_STYLES,
    FramePrompt,
    PartKind,
    Style,
    build_frame_prompt,
    load_styles,
)
from tests.storyboard.conftest import SENTINEL_RATIONALE, extraction_of, shot_of
from tools.build_samples import SAMPLES

K = PartKind
DEFAULT_BUDGET = 55
NO_BUDGET = 10_000
COUNTS = {"one figure", "two figures", "three figures", "four figures", "a group of figures"}
PREPOSITIONS = {"inside", "outside", "at"}

# Characters the samples name in action without ever giving them a cue; the cues supply the rest.
NON_SPEAKERS: dict[str, list[tuple[str, str]]] = {
    "the-red-kite": [],
    "lost-property": [("MARMALADE", "A ginger cat, MARMALADE, sleeps on a pile of lost scarves.")],
    "sipho-and-siphokazi": [],
}
PUBLIC = load_styles(PUBLIC_STYLES, None).public()


@cache
def sample(name: str) -> tuple[Screenplay, Extraction]:
    screenplay = parse_pdf((SAMPLES / f"{name}.pdf").read_bytes())
    return screenplay, extraction_of(screenplay, NON_SPEAKERS[name])


def characters(extraction: Extraction) -> list[str]:
    return [e.name for e in extraction.entities if e.kind is EntityKind.CHARACTER]


def every_shot(screenplay: Screenplay, extraction: Extraction) -> Iterator[Shot]:
    times = resolve_times(screenplay.scenes)
    framings = cycle(Framing)
    for scene in screenplay.scenes:
        cast = [
            e.name
            for e in extraction.entities
            if e.kind is EntityKind.CHARACTER and scene.index in e.scenes
        ]
        n = len(scene.elements)
        for first in range(n):
            for last in range(first, n):
                yield shot_of(
                    screenplay, scene.index, range(first, last + 1), characters=cast,
                    time_of_day=times[scene.index], framing=next(framings),
                    rationale=SENTINEL_RATIONALE,
                )  # fmt: skip


def clock_heading(screenplay: Screenplay, scene_index: int) -> Span | None:
    """Worked out here from the headings, independently of the code under test."""
    for scene in reversed(screenplay.scenes[: scene_index + 1]):
        if (scene.time_of_day or "").strip().upper() in ABSOLUTE_TIMES:
            return Span(scene.span.page, scene.span.line_start, scene.span.line_start)
    return None


def heading_line(screenplay: Screenplay, span: Span) -> str:
    return screenplay.text.split("\n")[span.line_start - 1]


def norm(text: str) -> str:
    return normalize_for_grounding(text)


def check(
    prompt: FramePrompt,
    shot: Shot,
    screenplay: Screenplay,
    extraction: Extraction,
    style: Style,
    max_words: int,
) -> None:
    scene = screenplay.scenes[shot.scene_index]
    names = characters(extraction)
    heading = Span(scene.span.page, scene.span.line_start, scene.span.line_start)
    covered = {scene.elements[i].span: scene.elements[i] for i in shot.elements}
    fixed = {
        K.STYLE: {f"{style.medium}, {style.finish}"},
        K.FRAMING: set(FRAMING_WORDS.values()),
        K.COUNT: COUNTS,
    }
    where = f"shot {shot.scene_index}.{shot.elements}"

    for part in prompt.parts:
        if part.span is None:
            assert part.text in fixed.get(part.kind, set()), f"{where}: unspanned {part}"
            continue
        text = part.text
        if part.kind is K.SETTING:
            assert part.span == heading, where
            preposition, text = text.split(" ", 1)
            assert preposition in PREPOSITIONS, where
            source = heading_line(screenplay, heading)
        elif part.kind is K.TIME:
            assert part.span == clock_heading(screenplay, scene.index), where
            # A closed vocabulary, never redacted: the clock word itself, from that heading.
            assert text.upper() in ABSOLUTE_TIMES, where
            assert norm(text) in norm(heading_line(screenplay, part.span)), where
            continue
        elif part.kind is K.ACTION:
            element = covered.get(part.span)
            assert isinstance(element, Action), f"{where}: {part} cites no covered action"
            source = element.text
        else:
            raise AssertionError(f"{where}: a {part.kind} part with a span")
        assert norm(text) in norm(redact_all(source, names)), f"{where}: {part}"

    whole = prompt.text()
    # No name, in the form screenplays write names (a lower-case common word is not one).
    tokens = name_tokens(names)
    named = [w for w in re.findall(r"\w+", whole) if w.upper() in tokens and w[0].isupper()]
    assert not named, f"{where}: names {named} in {whole!r}"
    # No speech and no parenthetical, from anywhere in the script, unless a covered action line
    # happens to say the same words (both redacted: "Van Wyk." and "VAN WYK" are "a person").
    actions = " | ".join(
        norm(redact_all(e.text, names)) for e in covered.values() if isinstance(e, Action)
    )
    for other in screenplay.scenes:
        for element in other.elements:
            if not isinstance(element, Dialogue):
                continue
            for said in (element.text, element.parenthetical or ""):
                if len(said.split()) >= 2 and norm(redact_all(said, names)) not in actions:
                    assert norm(redact_all(said, names)) not in norm(whole), f"{where}: {said!r}"
    assert norm(SENTINEL_RATIONALE) not in norm(whole)
    assert len(whole.split()) <= max_words


@pytest.mark.parametrize("budget", [DEFAULT_BUDGET, NO_BUDGET])
@pytest.mark.parametrize("style", PUBLIC, ids=[s.key for s in PUBLIC])
@pytest.mark.parametrize("name", sorted(NON_SPEAKERS))
def test_every_script_part_of_every_prompt_cites_this_shot(
    name: str, style: Style, budget: int
) -> None:
    screenplay, extraction = sample(name)
    shots = 0
    for shot in every_shot(screenplay, extraction):
        prompt = build_frame_prompt(shot, screenplay, extraction, style, max_words=budget)
        check(prompt, shot, screenplay, extraction, style, budget)
        shots += 1
    assert shots > 0


def test_the_samples_cover_what_the_invariant_must_see() -> None:
    """A CONTINUOUS scene after a night scene (a borrowed clock), a heading with no time, a
    possessive name in a heading, V.O. and O.S. speakers, and parentheticals."""
    red_kite, _ = sample("the-red-kite")
    lost, _ = sample("lost-property")
    sipho, _ = sample("sipho-and-siphokazi")
    times = [s.time_of_day for s in lost.scenes]
    assert any(a == "NIGHT" and b == "CONTINUOUS" for a, b in pairwise(times))
    assert any(s.time_of_day is None for s in sipho.scenes)
    assert any("'S " in s.location for s in (*red_kite.scenes, *sipho.scenes))
    speeches = [e for s in red_kite.scenes for e in s.elements if isinstance(e, Dialogue)]
    assert {"V.O.", "O.S."} <= {d.extension for d in speeches}
    assert any(d.parenthetical for d in speeches)


def test_budgeted_prompts_really_are_trimmed_somewhere() -> None:
    """The default budget must exercise the trimming path, or the invariant never saw a cut."""
    screenplay, extraction = sample("lost-property")
    trimmed = [
        build_frame_prompt(s, screenplay, extraction, PUBLIC[0], max_words=DEFAULT_BUDGET).trimmed
        for s in every_shot(screenplay, extraction)
    ]
    assert any(trimmed)
