"""normalize_for_grounding, locate, ground: grounding.md §3, §4, §9. Pure, no network."""

from collections.abc import Sequence

import pytest

from app.grounding import (
    Entity,
    EntityKind,
    ProposedEntity,
    Source,
    ground,
    locate,
    normalize_for_grounding,
)
from app.script import Screenplay, Span, parse_text
from tests.script.conftest import two_page_text


@pytest.fixture
def screenplay() -> Screenplay:
    text, breaks = two_page_text()
    return parse_text(text, breaks)


def proposal(kind: str, name: str, *quotes: str) -> ProposedEntity:
    return ProposedEntity.model_validate({"kind": kind, "name": name, "quotes": list(quotes)})


# --- normalisation and location ------------------------------------------------------


def test_normalisation_joins_line_break_hyphens_and_ignores_case_and_spacing() -> None:
    assert normalize_for_grounding("a broad-\n   shouldered  Man") == "A BROAD-SHOULDERED MAN"


def test_a_quote_across_a_wrapped_line_is_located_at_its_paragraph(screenplay: Screenplay) -> None:
    found = locate("nandi (60s, oilskin coat) pours tea", screenplay)
    assert found == (0, Span(page=1, line_start=7, line_end=8))


def test_a_quote_straddling_two_elements_is_not_located(screenplay: Screenplay) -> None:
    assert locate("You came back. The boat didn't.", screenplay) is None


def test_a_heading_is_locatable_at_its_own_line(screenplay: Screenplay) -> None:
    assert locate("LIGHTHOUSE STAIRWELL", screenplay) == (
        2,
        Span(page=2, line_start=35, line_end=35),
    )


def test_an_invented_or_empty_quote_is_not_located(screenplay: Screenplay) -> None:
    assert locate("the lighthouse keeper weeps", screenplay) is None
    assert locate("   ", screenplay) is None


# --- the filter ---------------------------------------------------------------------

PROPOSALS = [
    proposal(
        "character",
        "NANDI",
        "NANDI (60s, oilskin coat) pours tea into two chipped mugs.",
        "a line she never says",
    ),
    proposal("character", "THABO", "holding a torn map"),
    proposal("prop", "torn map", "holding a torn map."),
    proposal("character", "MARIA", "Maria waves."),
    proposal("prop", "window", "the window shatters"),
    proposal("character", "Thabo", "THABO steps out into the wind"),  # same character, later chunk
]


def by_name(entities: Sequence[Entity], kind: EntityKind) -> dict[str, Entity]:
    return {e.name: e for e in entities if e.kind is kind}


def test_every_kept_quote_is_located_and_bad_quotes_are_dropped(screenplay: Screenplay) -> None:
    entities, _ = ground(PROPOSALS, screenplay)
    nandi = by_name(entities, EntityKind.CHARACTER)["NANDI"]

    assert [q.text for q in nandi.quotes] == [
        "NANDI (60s, oilskin coat) pours tea into two chipped mugs."
    ]
    lines = screenplay.text.split("\n")
    for entity in entities:
        for q in entity.quotes:
            source = " ".join(lines[q.span.line_start - 1 : q.span.line_end])
            assert normalize_for_grounding(q.text) in normalize_for_grounding(source)


def test_the_same_entity_from_two_chunks_is_merged(screenplay: Screenplay) -> None:
    entities, _ = ground(PROPOSALS, screenplay)
    thabo = by_name(entities, EntityKind.CHARACTER)["THABO"]

    assert len(thabo.quotes) == 2
    assert thabo.source is Source.MODEL
    assert thabo.scenes == (0, 1)  # quoted in scene 1; speaks (O.S.) in scene 0


def test_unfounded_entities_are_dropped_with_a_reason(screenplay: Screenplay) -> None:
    entities, report = ground(PROPOSALS, screenplay)
    names = {e.name for e in entities}

    assert "MARIA" not in names and "window" not in names
    assert {(d.name, d.reason) for d in report.dropped} == {
        ("MARIA", "name not found in the script"),
        ("window", "no quote found in the script"),
    }


def test_locations_come_from_headings(screenplay: Screenplay) -> None:
    entities, _ = ground([], screenplay)
    locations = [e for e in entities if e.kind is EntityKind.LOCATION]

    assert [(e.name, e.scenes, e.source) for e in locations] == [
        ("LIGHTHOUSE KITCHEN", (0,), Source.HEADING),
        ("LIGHTHOUSE GALLERY", (1,), Source.HEADING),
        ("LIGHTHOUSE STAIRWELL", (2,), Source.HEADING),
    ]
    assert locations[0].quotes[0].span == Span(page=1, line_start=5, line_end=5)


def test_faithfulness_counts_entities_whose_name_and_every_quote_are_grounded(
    screenplay: Screenplay,
) -> None:
    _, report = ground(PROPOSALS, screenplay)

    # Proposed after merging: NANDI, THABO, torn map, MARIA, window.
    # Fully grounded: THABO and torn map (NANDI has one bad quote).
    assert (report.entities_proposed, report.entities_grounded) == (5, 2)
    assert report.faithfulness == pytest.approx(0.4)
    assert (report.quotes_proposed, report.quotes_located) == (7, 4)


def test_recall_measures_the_model_and_missed_speakers_are_backfilled_from_cues(
    screenplay: Screenplay,
) -> None:
    entities, report = ground([proposal("character", "THABO", "holding a torn map")], screenplay)
    nandi = by_name(entities, EntityKind.CHARACTER)["NANDI"]

    assert (report.cues_total, report.cues_found_by_model, report.recall) == (2, 1, 0.5)
    assert nandi.source is Source.CUE
    assert [q.text for q in nandi.quotes] == ["You came back."]
    assert nandi.scenes == (0,)


def test_full_recall_when_the_model_finds_every_speaker(screenplay: Screenplay) -> None:
    _, report = ground(PROPOSALS, screenplay)
    assert (report.cues_total, report.cues_found_by_model, report.recall) == (2, 2, 1.0)


def test_nothing_proposed_scores_one_not_zero(screenplay: Screenplay) -> None:
    _, report = ground([], screenplay)
    assert report.faithfulness == 1.0
    assert report.entities_proposed == 0
