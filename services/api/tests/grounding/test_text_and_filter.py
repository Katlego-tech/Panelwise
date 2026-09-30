"""normalize_for_grounding, locate, ground: grounding.md §3, §4, §9. Pure, no network."""

from collections.abc import Sequence

import pytest

from app.grounding import (
    Entity,
    EntityKind,
    ProposedEntity,
    Source,
    build_cue_index,
    build_index,
    ground,
    locate,
    locate_quote,
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


def test_a_spaced_dash_at_the_end_of_a_line_is_not_a_line_break_hyphen() -> None:
    # T039: "sign: LOST PROPERTY -" / "PLATFORM 9." was joined to "PROPERTY -PLATFORM", so the
    # sign's own words were "not found in the script". Only a hyphen touching a word is joined.
    assert normalize_for_grounding("LOST PROPERTY -\nPLATFORM 9") == "LOST PROPERTY - PLATFORM 9"
    assert normalize_for_grounding("sea-\n  green") == "SEA-GREEN"
    assert normalize_for_grounding("wait--\nnow") == "WAIT-NOW"


def test_typographic_punctuation_matches_its_plain_form(screenplay: Screenplay) -> None:
    # Models "prettify" punctuation: a curly apostrophe or an em dash is the same quote.
    assert locate("The boat didn\u2019t.", screenplay) == (
        0,
        Span(page=1, line_start=17, line_end=18),
    )
    assert locate("LIGHTHOUSE GALLERY \u2014 CONTINUOUS", screenplay) is not None
    assert (
        normalize_for_grounding("\u201cSo\u2026\u201d \u2018he\u2019 said") == "\"SO...\" 'HE' SAID"
    )


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


# --- a dialogue quote that starts with its own cue (T039) ----------------------------
# The model reads each speech as `CUE (EXT)` / `(parenthetical)` / text (render_chunk) and often
# copies the header lines too. The header is stripped only when it is exactly the header of the
# speech the rest is found in; the kept text is the rest, which is verbatim script text.


def find(screenplay: Screenplay, quote: str) -> tuple[str, int, Span] | None:
    return locate_quote(build_index(screenplay), build_cue_index(screenplay), quote)


@pytest.mark.parametrize(
    ("quote", "kept", "span"),
    [
        ("NANDI\nYou came back.", "You came back.", Span(1, 14, 14)),
        ("NANDI\n(without turning)\nYou came back.", "You came back.", Span(1, 14, 14)),
        ("NANDI (without turning)\nYou came back.", "You came back.", Span(1, 14, 14)),
        ("THABO (O.S.)\nThe boat didn't. I walked", "The boat didn't. I walked", Span(1, 17, 18)),
        ("thabo\nthe boat didn't.", "the boat didn't.", Span(1, 17, 18)),
        ("THABO\n(beat)\nAll of it.", "All of it.", Span(1, 29, 29)),
        ("THABO (CONT'D)\nThe whole coast.", "The whole coast.", Span(2, 33, 33)),
        # Live, once the prompt said "no cue", Lightning still led with the parenthetical.
        ("(without turning)\nYou came back.", "You came back.", Span(1, 14, 14)),
        ("(beat)\nAll of it.", "All of it.", Span(1, 29, 29)),
    ],
)
def test_a_speechs_own_cue_line_is_stripped_and_the_rest_kept_at_that_speech(
    screenplay: Screenplay, quote: str, kept: str, span: Span
) -> None:
    found = find(screenplay, quote)
    assert found is not None
    text, _, where = found
    assert (text, where) == (kept, span)
    lines = screenplay.text.split("\n")
    source = "\n".join(lines[where.line_start - 1 : where.line_end])
    assert normalize_for_grounding(text) in normalize_for_grounding(source)


@pytest.mark.parametrize(
    "quote",
    [
        "NANDI\nThe boat didn't.",  # someone else's speech
        "NANDI (O.S.)\nYou came back.",  # not this speech's extension
        "NANDI\n(smiling)\nYou came back.",  # not this speech's parenthetical
        "NANDI (smiling)\nYou came back.",
        "(beat)\nYou came back.",  # someone else's parenthetical
        "(without turning)\nThe boat didn't.",
        "(smiling)\nYou came back.",
        "NANDI (without turning)\n  ",  # nothing after the header
        "NANDI\n(without turning)",
        "NANDI You came back.",  # the cue must be its own line
        "NANDI: You came back.",
        "THABO\nIt's gone. All of it.",  # stitched across two speeches
        "NANDI\nYou came back.\nTHABO (O.S.)\nThe boat didn't.",
        "NANDI\nYou came home.",  # not what she says
        "INT. LIGHTHOUSE KITCHEN - NIGHT\nRain hammers the window.",  # a heading is not a cue
        "Rain hammers the window.\nDOORS SLAM.",  # an action line is not a cue
        "RADIO\nYou came back.",  # a name that is no cue at all
    ],
)
def test_nothing_else_is_loosened(screenplay: Screenplay, quote: str) -> None:
    assert find(screenplay, quote) is None


def test_a_quote_located_as_is_is_kept_as_is(screenplay: Screenplay) -> None:
    assert find(screenplay, "holding a torn map") == ("holding a torn map", 1, Span(1, 24, 24))


def test_the_filter_keeps_the_stripped_quote_and_counts_it_located(
    screenplay: Screenplay,
) -> None:
    entities, report = ground(
        [
            proposal("character", "NANDI", "NANDI\n(without turning)\nYou came back."),
            proposal("character", "THABO", "THABO (O.S.)\nThe boat didn't.", "NANDI\nAll of it."),
        ],
        screenplay,
    )
    cast = by_name(entities, EntityKind.CHARACTER)

    assert [(q.text, q.span) for q in cast["NANDI"].quotes] == [("You came back.", Span(1, 14, 14))]
    assert [q.text for q in cast["THABO"].quotes] == ["The boat didn't."]
    assert (report.quotes_proposed, report.quotes_located) == (3, 2)
    assert (report.entities_grounded, report.recall) == (1, 1.0)


def test_a_quote_given_with_and_without_its_cue_is_kept_once(screenplay: Screenplay) -> None:
    entities, report = ground(
        [
            proposal("character", "NANDI", "You came back.", "NANDI\nYou came back."),
            proposal("prop", "torn map", "a torn map", "a torn map"),  # Lightning repeats itself
        ],
        screenplay,
    )
    assert [q.text for q in by_name(entities, EntityKind.CHARACTER)["NANDI"].quotes] == [
        "You came back."
    ]
    assert len(by_name(entities, EntityKind.PROP)["torn map"].quotes) == 1
    # Kept once, but every quote was located: both entities are fully grounded.
    assert (report.entities_grounded, report.faithfulness) == (2, 1.0)


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
