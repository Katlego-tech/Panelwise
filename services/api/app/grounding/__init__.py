"""Grounded entity extraction. Design: docs/design/grounding.md."""

from app.grounding.extract import SYSTEM_PROMPT, chunk_scenes, extract, render_chunk
from app.grounding.filter import ground
from app.grounding.model import (
    Dropped,
    Entity,
    EntityKind,
    Extraction,
    ExtractionError,
    GroundingReport,
    Quote,
    Source,
)
from app.grounding.schema import ChunkEntities, ProposedEntity
from app.grounding.text import build_index, locate, locate_in, normalize_for_grounding

__all__ = [
    "SYSTEM_PROMPT",
    "ChunkEntities",
    "Dropped",
    "Entity",
    "EntityKind",
    "Extraction",
    "ExtractionError",
    "GroundingReport",
    "ProposedEntity",
    "Quote",
    "Source",
    "build_index",
    "chunk_scenes",
    "extract",
    "ground",
    "locate",
    "locate_in",
    "normalize_for_grounding",
    "render_chunk",
]
