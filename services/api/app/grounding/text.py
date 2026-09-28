"""Comparing a model's quote with the screenplay, and finding where it sits.

`normalize_for_grounding` is ported from FrameFlow's grounding.py. Screenplays are hard-wrapped,
so an accurate quote comes back with the wrap collapsed to a space, and a compound split across a
line break ("broad-" / "shouldered") comes back joined. Ignoring whitespace amount, case, and a
line-break hyphen does not weaken grounding: the complete word sequence must still appear, in
order. Invented or re-ordered content still fails. FrameFlow's lead character was dropped from
two runs in three by a line-break hyphen before this was fixed.
"""

import re

from app.script import Screenplay, Span

_WHITESPACE = re.compile(r"\s+")
_LINEBREAK_HYPHEN = re.compile(r"-[ \t]*\r?\n[ \t]*")


def normalize_for_grounding(text: str) -> str:
    joined = _LINEBREAK_HYPHEN.sub("-", text or "")
    return _WHITESPACE.sub(" ", joined).strip().upper()


type Index = list[tuple[int, Span, str]]


def build_index(screenplay: Screenplay) -> Index:
    """Every heading and element in script order, with its normalised source text.

    Built from the raw lines a span names (not the joined element text), so a line-break hyphen
    is still a line break here and gets joined.
    """
    lines = screenplay.text.split("\n")
    index: Index = []
    for scene in screenplay.scenes:
        heading = Span(scene.span.page, scene.span.line_start, scene.span.line_start)
        for span in (heading, *(e.span for e in scene.elements)):
            source = "\n".join(lines[span.line_start - 1 : span.line_end])
            index.append((scene.index, span, normalize_for_grounding(source)))
    return index


def locate_in(index: Index, quote: str) -> tuple[int, Span] | None:
    needle = normalize_for_grounding(quote)
    if not needle:
        return None
    for scene_index, span, text in index:
        if needle in text:
            return scene_index, span
    return None


def locate(quote: str, screenplay: Screenplay) -> tuple[int, Span] | None:
    """The first scene heading or element, in script order, whose text contains the quote.

    Only a match inside one element counts: a quote stitched across two speeches is not
    something the script says, and "somewhere in the script" is not a span a panel can cite.
    """
    return locate_in(build_index(screenplay), quote)
