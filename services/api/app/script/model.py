"""What a parsed screenplay is. docs/design/script.md §3.

Every element carries the page and lines it came from: Non-negotiable I (every panel traces
back to a verbatim span) is only possible if the parser kept one.
"""

from dataclasses import dataclass
from enum import StrEnum


class IntExt(StrEnum):
    INT = "INT"
    EXT = "EXT"
    INT_EXT = "INT/EXT"


class ScriptParseError(ValueError):
    """The input can't be read as a screenplay. Raised instead of returning an empty one."""


@dataclass(frozen=True)
class Span:
    """Where an element came from: `page` of its first line, and 1-based inclusive line numbers
    into `Screenplay.text`."""

    page: int
    line_start: int
    line_end: int


@dataclass(frozen=True)
class Action:
    text: str
    span: Span


@dataclass(frozen=True)
class Dialogue:
    cue: str
    extension: str | None
    parenthetical: str | None
    text: str
    span: Span


type Element = Action | Dialogue


@dataclass(frozen=True)
class Scene:
    index: int
    number: str
    heading: str
    int_ext: IntExt
    location: str
    time_of_day: str | None
    elements: tuple[Element, ...]
    span: Span


@dataclass(frozen=True)
class Screenplay:
    text: str
    page_count: int
    scenes: tuple[Scene, ...]
