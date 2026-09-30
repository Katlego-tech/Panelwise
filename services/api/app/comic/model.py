"""What a comic book is. docs/design/comic.md §3, §6.

Every lettered piece of text carries the `Span` it came from: Non-negotiable I (every panel
traces back to a verbatim span) holds for the words on the page as much as for the art.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.script import Span
from app.verify.model import Position

type Rect = tuple[int, int, int, int]  # x, y, w, h (page px)
type Point = tuple[int, int]  # x, y (page px)


class BubbleKind(StrEnum):
    SPEECH = "speech"
    OFF_PANEL = "off_panel"


class CaptionKind(StrEnum):
    SCENE = "scene"
    VOICE_OVER = "voice_over"


class ComicError(RuntimeError):
    """The comic can't be laid out or lettered without cutting script text; no partial book."""


@dataclass(frozen=True)
class Bubble:
    """One `Dialogue` element, lettered verbatim. `element` indexes `scene.elements`."""

    kind: BubbleKind
    speaker: str
    text: str
    element: int
    span: Span
    rect: Rect
    tail: Point | None
    font_px: int


@dataclass(frozen=True)
class Caption:
    """A scene caption (`element` None, span the heading) or a voice-over line."""

    kind: CaptionKind
    text: str
    element: int | None
    span: Span
    rect: Rect
    font_px: int


@dataclass(frozen=True)
class Panel:
    """One shot, named by `(scene_index, shot_number)`; its frame is rendered at `rect`'s size."""

    scene_index: int
    shot_number: int
    rect: Rect
    bubbles: tuple[Bubble, ...]
    captions: tuple[Caption, ...]


@dataclass(frozen=True)
class Page:
    number: int
    width: int
    height: int
    panels: tuple[Panel, ...]


@dataclass(frozen=True)
class LayoutReport:
    panels: int
    bubbles: int
    captions: int
    relayouts: int


@dataclass(frozen=True)
class ComicBook:
    pages: tuple[Page, ...]
    report: LayoutReport


@dataclass(frozen=True)
class WithheldCard:
    """What a withheld panel's card letters (comic.md §4 step 6): the failed checks and the span."""

    checks: str
    span: Span


@dataclass(frozen=True)
class PanelFrame:
    """A panel's frame, rendered at its rect's size. A withheld one is shown only as its card:
    `png` is never decoded when `withheld`, whatever it holds."""

    png: bytes
    positions: Mapping[str, Position]
    withheld: bool
    card: WithheldCard | None = None

    def __post_init__(self) -> None:
        if self.withheld != (self.card is not None):
            raise ComicError("a PanelFrame carries a withheld card exactly when it is withheld")
