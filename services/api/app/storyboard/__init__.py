"""Storyboard frames: styles and grounded frame prompts now; the renderer (T026) and the PDF
(T027) later. Design: docs/design/storyboard.md."""

from app.storyboard.prompt import (
    FRAMING_WORDS,
    OFF_SCREEN_MARKS,
    PLACEMENT_PHRASES,
    FramePrompt,
    PartKind,
    PromptError,
    PromptPart,
    build_frame_prompt,
    heading_span,
    time_source,
    visible_characters,
)
from app.storyboard.styles import (
    PUBLIC_STYLES,
    SUBJECT_WORDS,
    Style,
    StyleError,
    StyleOrigin,
    StyleRegistry,
    load_styles,
)

__all__ = [
    "FRAMING_WORDS",
    "OFF_SCREEN_MARKS",
    "PLACEMENT_PHRASES",
    "PUBLIC_STYLES",
    "SUBJECT_WORDS",
    "FramePrompt",
    "PartKind",
    "PromptError",
    "PromptPart",
    "Style",
    "StyleError",
    "StyleOrigin",
    "StyleRegistry",
    "build_frame_prompt",
    "heading_span",
    "load_styles",
    "time_source",
    "visible_characters",
]
