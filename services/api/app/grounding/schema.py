"""What the model is asked for, as a strict json_schema (findings U1: enforced on Nemotron).

Names and quotes only. No age, gender or role fields: those would be the model's inference, and
an inferred attribute is an invented one. A later stage that needs to draw a character reads its
quotes.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ProposedEntity(BaseModel):
    name: str = Field(description="The name exactly as the screenplay writes it")
    kind: Literal["character", "prop"]
    quotes: list[str] = Field(
        description=(
            "One to three excerpts copied character for character from a single action paragraph "
            "or a single line of dialogue, showing who or what this is"
        )
    )


class ChunkEntities(BaseModel):
    entities: list[ProposedEntity]
