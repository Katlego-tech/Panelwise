"""Lettering: which words go on a panel, and where. docs/design/comic.md §3, §4 steps 5-8.

Every bubble and caption letters a `Dialogue` element's text byte for byte, with that element's
span; the only other words are a scene's heading caption. Nothing is shortened: a box that finds
no room even at 28 px fails the comic, naming the shot, rather than lose a word.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageStat

from app.comic import layout
from app.comic.layout import PADDING, WRAP_SHARE, box_size, font_at, scene_caption
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
)
from app.script import Dialogue, Scene, Screenplay, Span, match_speaker
from app.shots import Shot, ShotPlan
from app.verify.model import Position

GRID_COLS, GRID_ROWS = 12, 8
FONT_SIZES = (32, 28)  # nominal, then the one smaller size; never lower
SPEAKER_COST = 2.0
SPEAKER_HEIGHT = Fraction(9, 20)  # a speaker's point is at 45% of the panel height

type Kind = BubbleKind | CaptionKind
type Cell = tuple[int, int]  # (row, col)


@dataclass(frozen=True)
class _Text:
    """One thing to letter, before it has a box."""

    kind: Kind
    speaker: str | None
    text: str
    element: int | None
    span: Span


@dataclass(frozen=True)
class _Placed:
    text: _Text
    rect: Rect
    cell: Cell
    font_px: int


def place_lettering(
    book: ComicBook,
    screenplay: Screenplay,
    plan: ShotPlan,
    frames: Mapping[tuple[int, int], PanelFrame],
) -> ComicBook:
    """Bubbles and captions for every panel, placed on its frame; the geometry is unchanged."""
    scenes = {scene.index: scene for scene in screenplay.scenes}
    shots = {(shot.scene_index, shot.number): shot for shot in plan.shots}
    firsts: dict[int, tuple[int, int]] = {}
    for shot in plan.shots:
        firsts.setdefault(shot.scene_index, (shot.scene_index, shot.number))

    pages: list[Page] = []
    bubbles = captions = 0
    for page in book.pages:
        panels: list[Panel] = []
        for panel in page.panels:
            key = (panel.scene_index, panel.shot_number)
            shot, scene = shots.get(key), scenes.get(panel.scene_index)
            if shot is None or scene is None:
                raise ComicError(
                    f"{panel_name(key)} is not in the shot plan or the screenplay", shot=key
                )
            frame = frames.get(key)
            if frame is None:
                raise ComicError(f"{panel_name(key)} has no frame", shot=key)
            texts = _texts(shot, scene, firsts[panel.scene_index] == key)
            placed = _place(panel, texts, frame)
            lettered = _lettered(panel, placed, frame)
            bubbles += len(lettered.bubbles)
            captions += len(lettered.captions)
            panels.append(lettered)
        pages.append(Page(page.number, page.width, page.height, tuple(panels)))
    report = LayoutReport(book.report.panels, bubbles, captions, book.report.relayouts)
    return ComicBook(tuple(pages), report)


def kind_of(extension: str | None) -> Kind:
    """comic.md §3: exhaustive over any extension, which is free text in the script."""
    upper = (extension or "").upper()
    if "V.O." in upper:
        return CaptionKind.VOICE_OVER
    if any(mark in upper for mark in ("O.S.", "O.C.", "OFF")):
        return BubbleKind.OFF_PANEL
    return BubbleKind.SPEECH


def _texts(shot: Shot, scene: Scene, first: bool) -> list[_Text]:
    texts: list[_Text] = []
    if first:
        heading = Span(scene.span.page, scene.span.line_start, scene.span.line_start)
        texts.append(_Text(CaptionKind.SCENE, None, scene_caption(scene), None, heading))
    for index in shot.elements:
        if not 0 <= index < len(scene.elements):
            raise ComicError(
                f"{panel_name((shot.scene_index, shot.number))} cites a missing element",
                shot=(shot.scene_index, shot.number),
            )
        element = scene.elements[index]
        if isinstance(element, Dialogue):  # action is never lettered; the art shows it
            kind = kind_of(element.extension)
            texts.append(_Text(kind, element.cue, element.text, index, element.span))
    return texts


def _place(panel: Panel, texts: Sequence[_Text], frame: PanelFrame) -> list[_Placed]:
    """comic.md §4 step 7: the cheapest admissible grid corner for each box, in order."""
    x, y, w, h = panel.rect
    key = (panel.scene_index, panel.shot_number)
    edges = None
    if not frame.withheld:
        edges = frame_image(frame.png, (w, h), key).convert("L").filter(ImageFilter.FIND_EDGES)
    positions: Mapping[str, Position] = {} if frame.withheld else frame.positions
    ix, iy, iw, ih = x + PADDING, y + PADDING, w - 2 * PADDING, h - 2 * PADDING
    corners = [
        ((row, col), ix + col * iw // GRID_COLS, iy + row * ih // GRID_ROWS)
        for row in range(GRID_ROWS)
        for col in range(GRID_COLS)
    ]
    limit = math.floor(w * WRAP_SHARE)
    placed: list[_Placed] = []
    for text in texts:
        missing = _missing_glyphs(text.text)
        if missing:
            raise ComicError(
                f"{panel_name(key)}: the lettering font has no glyph for {missing!r}, so "
                f"{text.text!r} can't be lettered as written",
                shot=key,
            )
        after = placed[-1].cell if placed else None
        third = _third(text.speaker, positions, w)
        choice: _Placed | None = None
        for size in FONT_SIZES:
            bw, bh = box_size(text.text, limit, font_at(layout.FONT_PATH, size))
            best: tuple[float, _Placed] | None = None
            for cell, cx, cy in corners:
                if after is not None and cell <= after:
                    continue  # reading order is hard
                if text.kind is CaptionKind.SCENE and cell != (0, 0):
                    continue  # the heading caption sits at the top-left
                rect = (cx, cy, bw, bh)
                if cx + bw > ix + iw or cy + bh > iy + ih:
                    continue
                if any(_overlap(rect, other.rect) for other in placed):
                    continue
                cost = _detail(edges, (cx - x, cy - y, bw, bh))
                if third is not None and cx - x < third[1] and cx - x + bw > third[0]:
                    cost += SPEAKER_COST
                if best is None or cost < best[0]:
                    best = (cost, _Placed(text, rect, cell, size))
            if best is not None:
                choice = best[1]
                break
        if choice is None:
            raise ComicError(
                f"{panel_name(key)}: no room to letter {text.text!r} even at {FONT_SIZES[-1]} px; "
                "the panel is too small for its lines, and no line is ever cut",
                shot=key,
            )
        placed.append(choice)
    return placed


def _lettered(panel: Panel, placed: Sequence[_Placed], frame: PanelFrame) -> Panel:
    positions: Mapping[str, Position] = {} if frame.withheld else frame.positions
    bubbles: list[Bubble] = []
    captions: list[Caption] = []
    for item in placed:
        text = item.text
        if isinstance(text.kind, CaptionKind):
            captions.append(
                Caption(text.kind, text.text, text.element, text.span, item.rect, item.font_px)
            )
            continue
        assert text.speaker is not None and text.element is not None
        tail = None  # on a card no one is in the panel, and a tail would cross its lines
        if not (frame.withheld and text.kind is BubbleKind.SPEECH):
            tail = _tail(text.kind, _position(text.speaker, positions), panel.rect, item.rect)
        bubbles.append(
            Bubble(
                text.kind,
                text.speaker,
                text.text,
                text.element,
                text.span,
                item.rect,
                tail,
                item.font_px,
            )
        )
    return Panel(panel.scene_index, panel.shot_number, panel.rect, tuple(bubbles), tuple(captions))


def _tail(kind: BubbleKind, position: Position | None, panel: Rect, box: Rect) -> Point:
    """comic.md §4 step 8: the tip, in page pixels, always inside the panel."""
    x, y, w, h = panel
    if kind is BubbleKind.OFF_PANEL:
        middle = box[1] + box[3] // 2
        return (x, middle) if position is Position.LEFT else (x + w - 1, middle)
    if position is None:
        return x + w // 2, y + h - 1
    centre = {Position.LEFT: w // 6, Position.CENTRE: w // 2, Position.RIGHT: 5 * w // 6}
    return x + centre[position], y + math.floor(h * SPEAKER_HEIGHT)


def _position(speaker: str | None, positions: Mapping[str, Position]) -> Position | None:
    if speaker is None:
        return None
    name = match_speaker(speaker, list(positions))
    return None if name is None else positions[name]


def _third(
    speaker: str | None, positions: Mapping[str, Position], w: int
) -> tuple[int, int] | None:
    """The speaker's third of the panel as panel-relative [start, end), or None when unknown."""
    position = _position(speaker, positions)
    if position is None:
        return None
    bounds = {
        Position.LEFT: (0, w // 3),
        Position.CENTRE: (w // 3, 2 * w // 3),
        Position.RIGHT: (2 * w // 3, w),
    }
    return bounds[position]


def frame_image(png: bytes, size: tuple[int, int], key: tuple[int, int]) -> Image.Image:
    """An accepted frame, decoded; it must be exactly its panel's size (comic.md §4 step 6)."""
    try:
        image = Image.open(BytesIO(png))
        image.load()
    except (OSError, ValueError) as error:
        raise ComicError(
            f"{panel_name(key)}: its frame is not a readable image", shot=key
        ) from error
    if image.size != size:
        raise ComicError(
            f"{panel_name(key)}: its frame is {image.size[0]} x {image.size[1]}, not its panel's "
            f"{size[0]} x {size[1]}; frames are rendered at the panel's size, never cropped",
            shot=key,
        )
    return image


def _detail(edges: Image.Image | None, box: Rect) -> float:
    """Mean edge strength over the box, 0-1; a withheld card has none."""
    if edges is None:
        return 0.0
    bx, by, bw, bh = box
    return ImageStat.Stat(edges.crop((bx, by, bx + bw, by + bh))).mean[0] / 255


def _missing_glyphs(text: str) -> str:
    """Characters the font would draw as its empty box: a word lettered as boxes is a word lost."""
    notdef = _glyph(layout.FONT_PATH, "\uffff")
    return "".join(
        sorted({ch for ch in text if not ch.isspace() and _glyph(layout.FONT_PATH, ch) == notdef})
    )


@cache
def _glyph(path: Path, ch: str) -> bytes:
    """A character as the font draws it, alone on a small canvas."""
    image = Image.new("L", (96, 96))
    ImageDraw.Draw(image).text((16, 16), ch, font=font_at(path, FONT_SIZES[0]), fill=255)
    return image.tobytes()


def _overlap(a: Rect, b: Rect) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def panel_name(key: tuple[int, int]) -> str:
    return f"scene {key[0]}, shot {key[1]}"
