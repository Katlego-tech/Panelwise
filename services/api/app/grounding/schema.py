"""What the model is asked for, as a strict json_schema (findings U1: enforced on Nemotron).

Names and quotes only. No age, gender or role fields: those would be the model's inference, and
an inferred attribute is an invented one. A later stage that needs to draw a character reads its
quotes. `species` and `other_names` are copied words, not attributes, and the filter grounds them
(grounding.md §3, T051).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _all_required(schema: dict[str, Any]) -> None:
    # Strict json_schema needs every property listed as required; the Python defaults only serve
    # callers that build a proposal by hand.
    schema["required"] = list(schema["properties"])


class ProposedEntity(BaseModel):
    model_config = ConfigDict(json_schema_extra=_all_required)

    name: str = Field(description="The name exactly as the screenplay writes it")
    kind: Literal["character", "prop"]
    quotes: list[str] = Field(
        description=(
            "One to three excerpts copied character for character from a single action paragraph "
            "or a single line of dialogue, showing who or what this is"
        )
    )
    species: str | None = Field(
        default=None,
        description=(
            "Only for a character that is an animal: the word the screenplay uses for what kind "
            "of animal it is, copied from one of the quotes. Null for a person and for every prop"
        ),
    )
    other_names: list[str] = Field(
        default_factory=list[str],
        description=(
            "Other names the screenplay gives this same character or prop (a nickname, a pet's "
            "or a toy's name), each copied exactly. Empty when there is none"
        ),
    )


class ChunkEntities(BaseModel):
    entities: list[ProposedEntity]
