"""The sample screenplays in samples/ (T031): each committed PDF is a fresh build of its source,
parses with the real parser, and reads the way samples/README.md says it does."""

import pytest

from app.script import Dialogue, Screenplay, parse_pdf
from tools.build_samples import OPTIONS, SAMPLES, build, speakers

NAMES = sorted(OPTIONS)


def committed(name: str) -> Screenplay:
    return parse_pdf((SAMPLES / f"{name}.pdf").read_bytes())


def readme_row(name: str) -> dict[str, str]:
    """The README table row for a sample, as {column header: cell}."""
    lines = (SAMPLES / "README.md").read_text(encoding="utf-8").splitlines()
    header = next(line for line in lines if line.startswith("| Sample |"))
    row = next(line for line in lines if line.startswith(f"| [`{name}`]"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    return dict(zip([h.strip() for h in header.strip("|").split("|")], cells, strict=True))


def test_every_sample_has_a_source_a_pdf_and_build_options() -> None:
    sources = {p.stem for p in SAMPLES.glob("*.fountain")}
    pdfs = {p.stem for p in SAMPLES.glob("*.pdf")}
    assert sources == pdfs == set(OPTIONS)


@pytest.mark.parametrize("name", NAMES)
def test_committed_pdf_is_a_fresh_build_of_its_source(name: str) -> None:
    # Compared as parsed, not as bytes: an fpdf2 upgrade may change the bytes, never the text.
    assert committed(name) == parse_pdf(build(name))


@pytest.mark.parametrize("name", NAMES)
def test_counts_match_the_readme(name: str) -> None:
    screenplay = committed(name)
    row = readme_row(name)
    assert int(row["Pages"]) == screenplay.page_count
    assert int(row["Scenes"]) == len(screenplay.scenes)
    assert int(row["Speaking characters"]) == len(speakers(screenplay))


@pytest.mark.parametrize("name", NAMES)
def test_every_element_span_slices_back_to_its_text(name: str) -> None:
    screenplay = committed(name)
    lines = screenplay.text.split("\n")
    for scene in screenplay.scenes:
        for element in scene.elements:
            source = lines[element.span.line_start - 1 : element.span.line_end]
            assert " ".join(line.strip() for line in source) == element.text


def test_the_demo_script_has_what_the_demo_shows() -> None:
    screenplay = committed("the-red-kite")
    times = {scene.time_of_day for scene in screenplay.scenes}
    assert {"DAY", "NIGHT", "CONTINUOUS"} <= times
    assert {scene.int_ext.value for scene in screenplay.scenes} == {"INT", "EXT"}
    speeches = [e for s in screenplay.scenes for e in s.elements if isinstance(e, Dialogue)]
    assert {"O.S.", "V.O.", "CONT'D"} <= {d.extension for d in speeches}
    assert any(d.parenthetical for d in speeches)
    # The (MORE) / (CONT'D) split: one speaker's speech continues at the top of the next page.
    split = next(i for i, d in enumerate(speeches) if d.extension == "CONT'D")
    before, after = speeches[split - 1], speeches[split]
    assert before.cue == after.cue
    assert after.span.page == before.span.page + 1
