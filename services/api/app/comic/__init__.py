"""Comic pages from a shot plan. Design: docs/design/comic.md."""

from app.comic.bubbles import kind_of, place_lettering
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
    PanelFrame,
    Point,
    Rect,
    WithheldCard,
)
from app.comic.render import panel_frame, render_pages, to_json, to_pdf, withheld_checks

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
    "PanelFrame",
    "Point",
    "Rect",
    "WithheldCard",
    "kind_of",
    "layout_geometry",
    "panel_frame",
    "panel_weight",
    "place_lettering",
    "render_pages",
    "scene_caption",
    "to_json",
    "to_pdf",
    "withheld_checks",
]
