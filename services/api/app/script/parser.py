"""Screenplay PDF -> ordered scenes whose every element knows where it came from.

docs/design/script.md §4. Ported from FrameFlow's screenplay_parser.py: pdfplumber's layout text
keeps each line's horizontal position, and in a screenplay the position *is* the structure --
a cue is identified by where it sits, not by guessing from ALL-CAPS ("DOORS SLAM." is action).

Changed for Panelwise: elements keep script order and a source span; wrapped lines are joined;
pages are real; a heading with no time gets None, not an invented DAY; the action margin is
anchored on the scene headings, so a dialogue-heavy script can't pull it to the dialogue column.
"""

import bisect
import io
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

import pdfplumber

from app.script.model import (
    Action,
    Dialogue,
    Element,
    IntExt,
    Scene,
    Screenplay,
    ScriptParseError,
    Span,
)

# Page furniture: in the text layer, not screenplay content.
_FURNITURE = re.compile(
    r"^\(?\s*(CONTINUED|MORE)\s*\)?[.:]?\s*(\(\d+\))?$|^\d{1,4}[.:]?$", re.IGNORECASE
)

# INT. / EXT. / INT/EXT. / EXT/INT. (dot optional), then the rest of the slug line.
SCENE_HEADING_RE = re.compile(r"^((?:INT|EXT)(?:\s*/\s*(?:INT|EXT))?\.?)\s+(.+)$", re.IGNORECASE)
_SCENE_NUMBER = re.compile(r"^(\d{1,4}[A-Za-z]?)\s+(?=(?:INT|EXT))", re.IGNORECASE)
_TIME_SPLIT = re.compile(r"\s*--+\s*|\s+-\s+")
_PARENTHETICAL = re.compile(r"^\((.+?)\)$")
_CUE_EXTENSION = re.compile(r"^(.*?)\s*\(([^)]*)\)\s*$")
_TRANSITIONS = frozenset(
    {"FADE IN", "FADE IN:", "FADE OUT", "FADE OUT.", "FADE OUT:", "FADE TO BLACK."}
)
_INDENT_PAST_MARGIN = 4  # a line this far right of the action margin belongs to dialogue
_FAR_RIGHT = 60  # page numbers and CONTINUED live out here; never the action margin


def parse_pdf(data: bytes) -> Screenplay:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page.extract_text(layout=True) or "" for page in pdf.pages]
    except Exception as exc:
        raise ScriptParseError(f"not a readable PDF ({type(exc).__name__})") from exc
    if not any(page.strip() for page in pages):
        raise ScriptParseError("no text layer (a scanned PDF needs OCR first)")

    lines: list[str] = []
    page_breaks: list[int] = []
    for number, page in enumerate(pages):
        if number:
            page_breaks.append(len(lines) + 1)
        # pdfplumber pads every row to the page width; the padding carries no information.
        lines.extend(line.rstrip() for line in page.split("\n"))
    return parse_text("\n".join(lines), page_breaks)


def parse_text(text: str, page_breaks: Sequence[int] = ()) -> Screenplay:
    lines = text.split("\n")
    breaks = sorted(page_breaks)
    return _Parser(lines, breaks, _action_margin(lines)).run(text, len(breaks) + 1)


@dataclass
class _Open:
    """The element being accumulated: consecutive lines of one action paragraph or one speech."""

    kind: type[Action] | type[Dialogue]
    first: int
    page: int
    cue: str | None = None
    extension: str | None = None
    parenthetical: str | None = None
    lines: list[str] = field(default_factory=list[str])
    last: int = 0

    def close(self) -> Element:
        span = Span(page=self.page, line_start=self.first, line_end=self.last)
        text = " ".join(self.lines)
        if self.kind is Dialogue:
            assert self.cue is not None
            return Dialogue(self.cue, self.extension, self.parenthetical, text, span)
        return Action(text, span)


@dataclass
class _OpenScene:
    index: int
    number: str
    heading: str
    int_ext: IntExt
    location: str
    time_of_day: str | None
    line: int
    page: int
    elements: list[Element] = field(default_factory=list[Element])

    def close(self) -> Scene:
        end = max([self.line, *(e.span.line_end for e in self.elements)])
        return Scene(
            index=self.index,
            number=self.number,
            heading=self.heading,
            int_ext=self.int_ext,
            location=self.location,
            time_of_day=self.time_of_day,
            elements=tuple(self.elements),
            span=Span(page=self.page, line_start=self.line, line_end=end),
        )


class _Parser:
    def __init__(self, lines: list[str], page_breaks: list[int], margin: int) -> None:
        self.lines = lines
        self.page_breaks = page_breaks
        self.margin = margin
        self.scenes: list[Scene] = []
        self.scene: _OpenScene | None = None
        self.open: _Open | None = None
        # The speaker a dialogue line belongs to, and the parenthetical waiting for their next line.
        self.cue: tuple[str, str | None] | None = None
        self.parenthetical: str | None = None
        # Cues sit right of dialogue; a shouted all-caps line ("NO!") at the dialogue column
        # must not read as a new speaker.
        self.cue_column: int | None = None

    def page_of(self, line_no: int) -> int:
        return bisect.bisect_right(self.page_breaks, line_no) + 1

    def run(self, text: str, page_count: int) -> Screenplay:
        page = 1
        for line_no, raw in enumerate(self.lines, 1):
            if self.page_of(line_no) != page:
                page = self.page_of(line_no)
                self.flush()  # an element never spans pages; the speaker carries over
            self.feed(line_no, page, raw)
        self.close_scene()
        if not self.scenes:
            raise ScriptParseError("no scene headings (INT./EXT.) found")
        return Screenplay(text=text, page_count=page_count, scenes=tuple(self.scenes))

    def feed(self, line_no: int, page: int, raw: str) -> None:
        if not raw.strip():
            self.flush()
            self.cue = self.parenthetical = None
            return
        indent = len(raw) - len(raw.lstrip())
        # Never rewrite a line: an element's text must be exactly the lines its span names.
        # A "CONTINUED: (2)" line is furniture and dropped whole; "Continued gunfire" is action.
        line = raw.strip()
        if _FURNITURE.match(line):
            return

        if self.start_scene(line_no, page, line):
            return
        if self.scene is None:  # title page
            return
        if _is_transition(line):
            self.flush()
            self.cue = self.parenthetical = None
            return

        indented = indent > self.margin + _INDENT_PAST_MARGIN
        if indented and (paren := _PARENTHETICAL.match(line)):
            self.flush()
            self.parenthetical = paren.group(1)
            return
        at_cue_column = self.cue_column is None or indent >= self.cue_column - 2
        if indented and at_cue_column and _is_cue(line):
            self.flush()
            self.cue = _split_cue(line)
            self.parenthetical = None
            self.cue_column = indent
            return
        if indented and self.cue is not None:
            self.append(Dialogue, line_no, page, line)
            return

        if self.cue is not None:
            self.flush()
            self.cue = self.parenthetical = None
        self.append(Action, line_no, page, line)

    def append(
        self, kind: type[Action] | type[Dialogue], line_no: int, page: int, line: str
    ) -> None:
        if self.open is None or self.open.kind is not kind:
            self.flush()
            self.open = _Open(kind=kind, first=line_no, page=page)
            if kind is Dialogue and self.cue is not None:
                self.open.cue, self.open.extension = self.cue
                self.open.parenthetical = self.parenthetical
        self.open.lines.append(line)
        self.open.last = line_no

    def flush(self) -> None:
        if self.open is not None and self.scene is not None:
            self.scene.elements.append(self.open.close())
        self.open = None

    def start_scene(self, line_no: int, page: int, line: str) -> bool:
        number: str | None = None
        if match := _SCENE_NUMBER.match(line):
            number = match.group(1)
            line = line[match.end() :].strip()
        heading = SCENE_HEADING_RE.match(line)
        if heading is None:
            return False

        self.close_scene()
        prefix, rest = heading.group(1).upper(), heading.group(2).strip()
        if number and (repeat := re.search(rf"\s{{2,}}{re.escape(number)}$", rest)):
            # Scripts repeat the scene number at the right edge of the row ("ROOM 1" is kept).
            rest = rest[: repeat.start()].rstrip()
        parts = _TIME_SPLIT.split(rest, maxsplit=1)
        location = parts[0].strip()
        time = parts[1].strip().upper() if len(parts) == 2 else ""
        self.scene = _OpenScene(
            index=len(self.scenes),
            number=number or str(len(self.scenes) + 1),
            heading=f"{prefix} {rest}",
            int_ext=IntExt.INT_EXT if "/" in prefix else IntExt(prefix.rstrip(".").strip()),
            location=location,
            time_of_day=time or None,
            line=line_no,
            page=page,
        )
        return True

    def close_scene(self) -> None:
        self.flush()
        self.cue = self.parenthetical = None
        if self.scene is not None:
            self.scenes.append(self.scene.close())
        self.scene = None


def _is_transition(line: str) -> bool:
    upper = line.upper()
    return upper in _TRANSITIONS or (line.isupper() and upper.endswith(("TO:", "TO BLACK.")))


def _is_cue(line: str) -> bool:
    return line.isupper() and len(line.split()) <= 5 and not _is_transition(line)


def _split_cue(line: str) -> tuple[str, str | None]:
    if match := _CUE_EXTENSION.match(line):
        return match.group(1).strip(), match.group(2).strip() or None
    return line, None


def _action_margin(lines: Sequence[str]) -> int:
    """The column action sits at. Scene headings always start there, so their column is the
    anchor; the most common indent is only the fallback, because in a talky script it is the
    dialogue column. Returns 0 for text with no indentation, which reads every line as action --
    conservative, rather than inventing characters."""
    headings: Counter[int] = Counter()
    indents: Counter[int] = Counter()
    for raw in lines:
        body = raw.lstrip()
        if not body or _FURNITURE.match(body.strip()):
            continue
        column = len(raw) - len(body)
        indents[column] += 1
        if match := _SCENE_NUMBER.match(body):
            column += match.end()
            body = body[match.end() :]
        if SCENE_HEADING_RE.match(body.strip()):
            headings[column] += 1
    if headings:
        return headings.most_common(1)[0][0]
    usable = [(count, col) for col, count in indents.items() if col < _FAR_RIGHT]
    return max(usable)[1] if usable else 0
