"""The two model calls, as strict json_schema. docs/design/verify.md §3, §6.

The describer's schema has no field for a name: it can only say what it sees. The judge's has
nothing but index calls and verbatim support, which code checks (verify.md §8).
"""

from pydantic import BaseModel, Field

from app.verify.model import Light, ObjectCategory, ObjectKind, Position, Setting, ShotSize


class SeenPerson(BaseModel):
    position: Position = Field(description="Where the person stands in the frame")
    appearance: str = Field(description="A short phrase: what the person looks like")


class SeenObject(BaseModel):
    name: str = Field(description="What the object is, in a word or two")
    category: ObjectCategory
    held: bool = Field(description="Whether someone in the frame holds it")


class FrameDescription(BaseModel):
    people: list[SeenPerson]
    setting: Setting
    light: Light
    shot_size: ShotSize
    objects: list[SeenObject]
    has_text: bool = Field(description="Whether any text, letters or numbers appear in the image")


class PersonCall(BaseModel):
    person: int = Field(description="0-based index into the description's people")
    character: str | None = Field(description="The shot character this person is, or null")
    support: str | None = Field(
        description="Only for a person who is no character: a verbatim quote that puts them there"
    )


class ObjectCall(BaseModel):
    object: int = Field(description="0-based index into the description's objects")
    kind: ObjectKind
    support: str | None = Field(
        description="A verbatim quote: the text or an entity quote for a scripted prop, the "
        "scene heading's words for set dressing"
    )


class Judgement(BaseModel):
    people: list[PersonCall]
    objects: list[ObjectCall]
