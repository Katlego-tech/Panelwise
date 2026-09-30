"""Comic pages from a shot plan. Design: docs/design/comic.md."""

from app.comic.layout import layout_geometry, panel_weight, scene_caption
from app.comic.model import (
    Bubble,
    BubbleKind,
    Caption,
    CaptionKind,
    ComicBook,
    ComicError,
    LayoutReport,
    Page,
    Panel,
    Point,
    Rect,
)

__all__ = [
    "Bubble",
    "BubbleKind",
    "Caption",
    "CaptionKind",
    "ComicBook",
    "ComicError",
    "LayoutReport",
    "Page",
    "Panel",
    "Point",
    "Rect",
    "layout_geometry",
    "panel_weight",
    "scene_caption",
]
