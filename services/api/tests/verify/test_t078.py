"""T078: a part of a shot's prop is that prop; the describer leaves out the drawing's own marks
(verify.md §3 A part of a prop, §6 `part_of_prop`, §9)."""

import pytest

from app.grounding import Extraction
from app.script import Screenplay
from app.verify import Check, part_of_prop, run_checks
from app.verify.prompts import DESCRIBE_PROMPT
from tests.verify.conftest import described, judged, kitchen_shot


@pytest.mark.parametrize(
    ("name", "props", "part"),
    [
        ("map corner", ("torn map",), "torn map"),
        ("torn map edge", ("torn map",), "torn map"),
        ("Map Corner", ("torn map",), "torn map"),  # compared in lower case
        ("map", ("torn map",), None),  # the prop itself, judged as before
        ("old map", ("torn map",), None),  # ends in the head noun: the prop or a copy
        ("second map corner", ("torn map",), None),  # a copy word
        ("another map edge", ("torn map",), None),
        ("oilskin bag", ("oilskin coat",), None),  # shares a word that isn't the head noun
        ("map corner", ("oilskin coat",), None),  # the map isn't in this shot
    ],
)
def test_part_of_prop(
    extraction: Extraction, name: str, props: tuple[str, ...], part: str | None
) -> None:
    assert part_of_prop(name, kitchen_shot(props=props), extraction) == part


def _checks(screenplay: Screenplay, extraction: Extraction, props: tuple[str, ...]) -> set[Check]:
    objects = [{"name": "map corner", "category": "other", "held": True}]
    calls = [{"object": 0, "kind": "unscripted", "support": None}]
    checks, _, _ = run_checks(
        kitchen_shot(props=props),
        screenplay.scenes[0],
        described(objects=objects),
        judged(objects=calls),
        extraction,
    )
    return {c.check for c in checks if not c.ok}


def test_a_held_part_called_unscripted_passes_when_its_prop_is_in_the_shot(
    screenplay: Screenplay, extraction: Extraction
) -> None:
    assert Check.UNSCRIPTED_OBJECT not in _checks(screenplay, extraction, ("torn map",))


def test_the_same_part_fails_when_its_prop_is_not_in_the_shot(
    screenplay: Screenplay, extraction: Extraction
) -> None:
    assert Check.UNSCRIPTED_OBJECT in _checks(screenplay, extraction, ("oilskin coat",))


def test_the_describer_leaves_out_the_drawing_s_own_marks() -> None:
    prompt = DESCRIBE_PROMPT.lower()
    for mark in ("shading", "hatching", "outlines", "border"):
        assert mark in prompt
