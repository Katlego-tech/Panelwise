"""Comic pages as pixels, a PDF and the reader's JSON. docs/design/comic.md §4 steps 6-8, §6.

A withheld frame is never drawn: its panel shows the withheld card, and `PanelFrame.withheld` is
the switch, so a withheld frame's bytes are never even decoded.
"""

import math
from collections.abc import Mapping, Sequence
from io import BytesIO

from PIL import Image, ImageDraw

from app.comic import layout
from app.comic.bubbles import frame_image, panel_name
from app.comic.layout import FONT_PX, PADDING, WRAP_SHARE, font_at, wrap
from app.comic.model import (
    Bubble,
    Caption,
    ComicBook,
    ComicError,
    Panel,
    PanelFrame,
    Point,
    Rect,
    WithheldCard,
)
from app.script import Span
from app.shots import Shot
from app.verify.model import Audit, Check, FrameOutcome, FrameState, Severity, Verdict

DPI = 300
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
CARD_GREY = (128, 128, 128)  # #808080
CAPTION_FILL = (255, 244, 194)  # #FFF4C2
PANEL_BORDER = CARD_BORDER = 4
OUTLINE = 3
MAX_RADIUS = 48
TAIL_BASE = 28

type Key = tuple[int, int]
type RGB = tuple[int, int, int]


def withheld_checks(audit: Audit) -> str:
    """The card's <checks>: `audit error`, or the failed hard checks in `Check` order."""
    if audit.verdict is Verdict.ERROR:
        return "audit error"
    failed = {r.check for r in audit.checks if r.severity is Severity.HARD and not r.ok}
    return ", ".join(check.value.replace("_", " ") for check in Check if check in failed)


def panel_frame(outcome: FrameOutcome, shot: Shot) -> PanelFrame:
    """verify's outcome as the comic needs it: the accepted frame, or only the card."""
    key = (shot.scene_index, shot.number)
    if outcome.shot != key:
        raise ComicError(f"{panel_name(key)} was given the outcome of {panel_name(outcome.shot)}")
    last = outcome.audits[-1] if outcome.audits else None
    if outcome.state in (FrameState.PASSED, FrameState.WARNED):
        if outcome.frame is None or last is None:
            raise ComicError(f"{panel_name(key)} is {outcome.state} without its frame and audit")
        return PanelFrame(outcome.frame.png, dict(last.positions), False)
    if outcome.state is FrameState.WITHHELD:
        checks = "" if last is None else withheld_checks(last)
        if not checks:
            raise ComicError(f"{panel_name(key)} is withheld without a failed hard check")
        return PanelFrame(b"", {}, True, WithheldCard(checks, shot.span))
    raise ComicError(f"{panel_name(key)}: its frame is {outcome.state}, not accepted or withheld")


def card_lines(card: WithheldCard) -> tuple[str, str]:
    span = card.span
    return (
        f"Frame withheld: failed audit ({card.checks})",
        f"Script p.{span.page} l.{span.line_start}\u2013{span.line_end}",  # an en dash
    )


def render_pages(book: ComicBook, frames: Mapping[Key, PanelFrame]) -> list[bytes]:
    """One PNG per page: each panel's frame (or card) at its rect, then its lettering."""
    out: list[bytes] = []
    for page in book.pages:
        canvas = Image.new("RGB", (page.width, page.height), WHITE)
        for panel in page.panels:
            key = (panel.scene_index, panel.shot_number)
            frame = frames.get(key)
            if frame is None:
                raise ComicError(f"{panel_name(key)} has no frame")
            canvas.paste(_tile(panel, frame, key), panel.rect[:2])
            _letter(ImageDraw.Draw(canvas), panel)
        buffer = BytesIO()
        canvas.save(buffer, "PNG")
        out.append(buffer.getvalue())
    return out


def to_pdf(pages: Sequence[bytes]) -> bytes:
    """One PDF page per page PNG, at 300 dpi: 1988 x 3075 px is the 6.625 x 10.25 in trim."""
    if not pages:
        raise ComicError("a comic PDF needs at least one page")
    images = [Image.open(BytesIO(page)).convert("RGB") for page in pages]
    buffer = BytesIO()
    images[0].save(buffer, "PDF", save_all=True, append_images=images[1:], resolution=DPI)
    return buffer.getvalue()


def to_json(book: ComicBook, frame_urls: Mapping[Key, str]) -> dict[str, object]:
    """T024's layout JSON (comic.md §6). A shot with no URL is withheld and has no frame_url."""
    return {
        "pages": [
            {
                "number": page.number,
                "width": page.width,
                "height": page.height,
                "panels": [_panel_json(panel, frame_urls) for panel in page.panels],
            }
            for page in book.pages
        ]
    }


def _panel_json(panel: Panel, frame_urls: Mapping[Key, str]) -> dict[str, object]:
    key = (panel.scene_index, panel.shot_number)
    out: dict[str, object] = {"shot": list(key), "rect": list(panel.rect)}
    url = frame_urls.get(key)
    if url is not None:
        out["frame_url"] = url
    out["withheld"] = url is None
    out["bubbles"] = [
        {
            "kind": b.kind.value,
            "speaker": b.speaker,
            "text": b.text,
            "element": b.element,
            "span": _span_json(b.span),
            "rect": list(b.rect),
            "tail": None if b.tail is None else list(b.tail),
            "font_px": b.font_px,
        }
        for b in panel.bubbles
    ]
    out["captions"] = [
        {
            "kind": c.kind.value,
            "text": c.text,
            "element": c.element,
            "span": _span_json(c.span),
            "rect": list(c.rect),
            "font_px": c.font_px,
        }
        for c in panel.captions
    ]
    return out


def _span_json(span: Span) -> dict[str, int]:
    return {"page": span.page, "line_start": span.line_start, "line_end": span.line_end}


def _tile(panel: Panel, frame: PanelFrame, key: Key) -> Image.Image:
    _, _, w, h = panel.rect
    if frame.withheld:
        assert frame.card is not None  # PanelFrame guarantees it
        return _card(w, h, frame.card)
    tile = frame_image(frame.png, (w, h), key).convert("RGB")
    ImageDraw.Draw(tile).rectangle((0, 0, w - 1, h - 1), outline=BLACK, width=PANEL_BORDER)
    return tile


def _card(w: int, h: int, card: WithheldCard) -> Image.Image:
    """comic.md §4 step 6: white, a grey border, two centred lines; never the frame's pixels."""
    image = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, w - 1, h - 1), outline=CARD_GREY, width=CARD_BORDER)
    font = font_at(layout.FONT_PATH, FONT_PX)
    ascent, descent = font.getmetrics()
    lines = [line for text in card_lines(card) for line in wrap(text, w - 2 * PADDING, font)]
    top = (h - len(lines) * (ascent + descent)) // 2
    for i, line in enumerate(lines):
        x = (w - font.getlength(line)) / 2
        draw.text((x, top + i * (ascent + descent)), line, font=font, fill=BLACK)
    return image


def _letter(draw: ImageDraw.ImageDraw, panel: Panel) -> None:
    """Every outline, then every fill, then every word: a tail under a bubble never hides text."""
    items: list[Bubble | Caption] = [*panel.captions, *panel.bubbles]
    tails = {id(b): _tail_polygon(b) for b in panel.bubbles}
    for item in items:
        x, y, w, h = item.rect
        grown = (x - OUTLINE, y - OUTLINE, x + w - 1 + OUTLINE, y + h - 1 + OUTLINE)
        if isinstance(item, Caption):
            draw.rectangle(grown, fill=BLACK)
            continue
        draw.rounded_rectangle(grown, radius=_radius(item.rect) + OUTLINE, fill=BLACK)
        polygon = tails[id(item)]
        if polygon is not None:
            draw.polygon(polygon, fill=BLACK)
            draw.line([*polygon, polygon[0]], fill=BLACK, width=2 * OUTLINE, joint="curve")
    for item in items:
        x, y, w, h = item.rect
        box = (x, y, x + w - 1, y + h - 1)
        if isinstance(item, Caption):
            draw.rectangle(box, fill=CAPTION_FILL)
            continue
        draw.rounded_rectangle(box, radius=_radius(item.rect), fill=WHITE)
        polygon = tails[id(item)]
        if polygon is not None:
            draw.polygon(polygon, fill=WHITE)
    limit = math.floor(panel.rect[2] * WRAP_SHARE)
    for item in items:
        x, y, w, _ = item.rect
        font = font_at(layout.FONT_PATH, item.font_px)
        ascent, descent = font.getmetrics()
        for i, line in enumerate(wrap(item.text, limit, font)):
            left = x + (w - font.getlength(line)) / 2
            draw.text((left, y + PADDING + i * (ascent + descent)), line, font=font, fill=BLACK)


def _radius(rect: Rect) -> int:
    return min(MAX_RADIUS, rect[3] // 2, rect[2] // 2)


def _tail_polygon(bubble: Bubble) -> list[tuple[float, float]] | None:
    """A triangle from inside the bubble to its tip; none when the tip is inside the box."""
    if bubble.tail is None:
        return None
    x, y, w, h = bubble.rect
    tx, ty = bubble.tail
    if x <= tx < x + w and y <= ty < y + h:
        return None
    r = _radius(bubble.rect)
    base: Point = (min(max(tx, x + r), x + w - 1 - r), min(max(ty, y + r), y + h - 1 - r))
    dx, dy = tx - base[0], ty - base[1]
    length = math.hypot(dx, dy)
    px, py = -dy / length * TAIL_BASE / 2, dx / length * TAIL_BASE / 2
    return [(base[0] + px, base[1] + py), (float(tx), float(ty)), (base[0] - px, base[1] - py)]
