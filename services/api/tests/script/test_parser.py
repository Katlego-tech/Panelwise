"""parse_text / parse_pdf -- docs/design/script.md §3, §4, §9."""

import pytest
from fpdf import FPDF

from app.script import (
    Action,
    Dialogue,
    IntExt,
    Screenplay,
    ScriptParseError,
    Span,
    parse_pdf,
    parse_text,
)

from .conftest import (
    ACTION,
    CUE,
    DIALOGUE,
    PAGE_1,
    PAGE_2,
    heading,
    layout,
    pdf_bytes,
    two_page_text,
)


@pytest.fixture
def screenplay() -> Screenplay:
    text, breaks = two_page_text()
    return parse_text(text, breaks)


def texts(screenplay: Screenplay, scene: int) -> list[str]:
    return [e.text for e in screenplay.scenes[scene].elements]


# --- scenes ------------------------------------------------------------------------


def test_scenes_come_out_in_order_with_the_scripts_own_numbers(screenplay: Screenplay) -> None:
    assert [(s.index, s.number) for s in screenplay.scenes] == [(0, "1"), (1, "2"), (2, "3")]
    assert screenplay.page_count == 2


def test_heading_fields_are_split_and_the_repeated_number_dropped(screenplay: Screenplay) -> None:
    first, second = screenplay.scenes[:2]
    assert (first.heading, first.int_ext, first.location, first.time_of_day) == (
        "INT. LIGHTHOUSE KITCHEN - NIGHT",
        IntExt.INT,
        "LIGHTHOUSE KITCHEN",
        "NIGHT",
    )
    assert (second.int_ext, second.location, second.time_of_day) == (
        IntExt.EXT,
        "LIGHTHOUSE GALLERY",
        "CONTINUOUS",
    )


def test_a_heading_without_a_time_has_none_rather_than_an_invented_day(
    screenplay: Screenplay,
) -> None:
    assert screenplay.scenes[2].time_of_day is None


@pytest.mark.parametrize(
    ("slug", "int_ext", "location", "time"),
    [
        ("INT/EXT. BAKKIE -- CONTINUOUS", IntExt.INT_EXT, "BAKKIE", "CONTINUOUS"),
        ("EXT/INT. FARMHOUSE - DAWN", IntExt.INT_EXT, "FARMHOUSE", "DAWN"),
        ("int. hallway -- later", IntExt.INT, "hallway", "LATER"),
        ("EXT. ROOFTOP--NIGHT", IntExt.EXT, "ROOFTOP", "NIGHT"),
    ],
)
def test_heading_variants(slug: str, int_ext: IntExt, location: str, time: str) -> None:
    scene = parse_text(layout([(ACTION, slug), (ACTION, "Something happens.")])).scenes[0]
    assert (scene.int_ext, scene.location, scene.time_of_day) == (int_ext, location, time)
    assert scene.number == "1"


# --- elements ----------------------------------------------------------------------


def test_elements_keep_script_order_and_join_wrapped_lines(screenplay: Screenplay) -> None:
    assert texts(screenplay, 0) == [
        "Rain hammers the window. NANDI (60s, oilskin coat) pours tea into two chipped mugs.",
        "DOORS SLAM.",
        "You came back.",
        "The boat didn't. I walked the last mile along the cliff.",
    ]
    kinds = [type(e) for e in screenplay.scenes[0].elements]
    assert kinds == [Action, Action, Dialogue, Dialogue]


def test_an_all_caps_line_at_the_action_margin_is_action_not_a_character(
    screenplay: Screenplay,
) -> None:
    doors = screenplay.scenes[0].elements[1]
    assert isinstance(doors, Action)


def test_cue_extension_and_parenthetical_are_separate_fields(screenplay: Screenplay) -> None:
    nandi, thabo = screenplay.scenes[0].elements[2:]
    assert isinstance(nandi, Dialogue) and isinstance(thabo, Dialogue)
    assert (nandi.cue, nandi.extension, nandi.parenthetical) == ("NANDI", None, "without turning")
    assert (thabo.cue, thabo.extension, thabo.parenthetical) == ("THABO", "O.S.", None)


def test_a_parenthetical_mid_speech_starts_a_new_dialogue_for_the_same_cue(
    screenplay: Screenplay,
) -> None:
    speeches = [e for e in screenplay.scenes[1].elements if isinstance(e, Dialogue)]
    assert [(d.cue, d.extension, d.parenthetical, d.text) for d in speeches] == [
        ("THABO", None, None, "It's gone."),
        ("THABO", None, "beat", "All of it."),
        ("THABO", "CONT'D", None, "The whole coast."),
    ]


def test_title_page_transitions_and_page_furniture_are_not_content(
    screenplay: Screenplay,
) -> None:
    everything = " ".join(e.text for s in screenplay.scenes for e in s.elements)
    for noise in ("THE KEEPER'S LIGHT", "FADE IN", "CUT TO", "MORE", "2."):
        assert noise not in everything


def test_dialogue_continuing_onto_a_new_page_without_a_cue_stays_dialogue() -> None:
    rows = [heading("1", "INT. ROOM - DAY"), None, (CUE, "NANDI"), (DIALOGUE, "One more")]
    text = layout([*rows, (DIALOGUE, "thing.")])
    scene = parse_text(text, [len(rows) + 1]).scenes[0]

    assert [(type(e), e.text, e.span.page) for e in scene.elements] == [
        (Dialogue, "One more", 1),
        (Dialogue, "thing.", 2),
    ]


def test_shouted_all_caps_dialogue_is_not_mistaken_for_a_new_speaker() -> None:
    rows = [
        heading("1", "INT. ROOM - DAY"),
        None,
        (CUE, "NANDI"),
        (DIALOGUE, "NO!"),
        None,
        (CUE, "THABO"),
        (DIALOGUE, "Yes."),
    ]
    elements = parse_text(layout(rows)).scenes[0].elements

    assert [(type(e), getattr(e, "cue", None), e.text) for e in elements] == [
        (Dialogue, "NANDI", "NO!"),
        (Dialogue, "THABO", "Yes."),
    ]


def test_a_location_ending_in_the_scene_number_keeps_it() -> None:
    scene = parse_text(layout([(ACTION, "1 INT. ROOM 1 - DAY"), (ACTION, "A chair.")])).scenes[0]
    assert (scene.number, scene.location) == ("1", "ROOM 1")


def test_a_dialogue_heavy_script_still_finds_the_action_margin() -> None:
    # More dialogue lines than action lines: the most common indent is the dialogue column.
    rows = [heading("1", "INT. OFFICE - DAY"), None, (ACTION, "They sit.")]
    for i in range(6):
        rows += [None, (CUE, "AMARA" if i % 2 else "JONAS"), (DIALOGUE, f"Line {i}.")]
    scene = parse_text(layout(rows)).scenes[0]

    assert [type(e) for e in scene.elements] == [Action] + [Dialogue] * 6


# --- spans -------------------------------------------------------------------------


def test_a_line_that_starts_with_continued_keeps_every_word() -> None:
    rows = [
        heading("1", "INT. VALLEY - DAY"),
        None,
        (ACTION, "Continued gunfire echoes."),
        None,
        (ACTION, "CONTINUED: (2)"),
        (ACTION, "CONTINUED: INT. VALLEY - DAY"),
    ]
    screenplay = parse_text(layout(rows))

    assert len(screenplay.scenes) == 1  # a merged CONTINUED: heading is not a second scene
    first = screenplay.scenes[0].elements[0]
    assert first.text == "Continued gunfire echoes."
    for e in screenplay.scenes[0].elements:
        source = screenplay.text.split("\n")[e.span.line_start - 1 : e.span.line_end]
        assert " ".join(line.strip() for line in source) == e.text


def test_every_element_span_slices_back_to_exactly_its_text(screenplay: Screenplay) -> None:
    lines = screenplay.text.split("\n")
    for scene in screenplay.scenes:
        for element in scene.elements:
            source = lines[element.span.line_start - 1 : element.span.line_end]
            assert " ".join(line.strip() for line in source) == element.text


def test_spans_report_the_real_page(screenplay: Screenplay) -> None:
    last_speech = screenplay.scenes[1].elements[-1]
    assert last_speech.span.page == 2
    assert screenplay.scenes[2].span == Span(
        page=2, line_start=len(PAGE_1) + 5, line_end=len(PAGE_1) + 7
    )
    assert screenplay.scenes[0].elements[0].span == Span(page=1, line_start=7, line_end=8)


# --- errors ------------------------------------------------------------------------


def test_text_with_no_scene_headings_is_an_error_not_an_empty_screenplay() -> None:
    with pytest.raises(ScriptParseError, match="no scene headings"):
        parse_text(layout([(ACTION, "Just some prose."), (ACTION, "No headings at all.")]))


def test_a_pdf_with_no_text_layer_is_an_error() -> None:
    pdf = FPDF(format="letter")
    pdf.add_page()
    pdf.rect(20, 20, 50, 50)  # drawn, not written: no text layer
    with pytest.raises(ScriptParseError, match="no text layer"):
        parse_pdf(bytes(pdf.output()))


def test_bytes_that_are_not_a_pdf_are_an_error() -> None:
    with pytest.raises(ScriptParseError, match="not a readable PDF"):
        parse_pdf(b"this is not a pdf")


# --- end to end ----------------------------------------------------------------------


def test_a_real_two_page_pdf_parses_like_its_layout_text() -> None:
    parsed = parse_pdf(pdf_bytes([PAGE_1, PAGE_2]))
    text, breaks = two_page_text()
    expected = parse_text(text, breaks)

    assert parsed.page_count == 2
    assert [s.heading for s in parsed.scenes] == [s.heading for s in expected.scenes]
    assert [[type(e) for e in s.elements] for s in parsed.scenes] == [
        [type(e) for e in s.elements] for s in expected.scenes
    ]
    assert [[e.text for e in s.elements] for s in parsed.scenes] == [
        [e.text for e in s.elements] for s in expected.scenes
    ]
    assert parsed.scenes[1].elements[-1].span.page == 2
    lines = parsed.text.split("\n")
    for scene in parsed.scenes:
        for e in scene.elements:
            source = lines[e.span.line_start - 1 : e.span.line_end]
            assert " ".join(line.strip() for line in source) == e.text
