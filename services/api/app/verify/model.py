"""What a frame audit is. docs/design/verify.md §3, §6.

`RenderedFrame` and `Renderer` are the shapes T008's renderer provides: verify depends on them and
nothing more, so the audit runs on any PNG, rendered or not.
"""

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Protocol

from app.llm import Usage
from app.shots import Shot

if TYPE_CHECKING:
    from app.verify.schema import FrameDescription, Judgement


class Position(StrEnum):
    LEFT = "left"
    CENTRE = "centre"
    RIGHT = "right"


class Setting(StrEnum):
    INTERIOR = "interior"
    EXTERIOR = "exterior"
    UNCLEAR = "unclear"


class Light(StrEnum):
    DAY = "day"
    NIGHT = "night"
    DAWN_OR_DUSK = "dawn_or_dusk"
    UNCLEAR = "unclear"


class ShotSize(StrEnum):
    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE = "close"
    EXTREME_CLOSE = "extreme_close"
    UNCLEAR = "unclear"


class ObjectKind(StrEnum):
    SCRIPTED_PROP = "scripted_prop"
    SET_DRESSING = "set_dressing"
    UNSCRIPTED = "unscripted"


class ObjectCategory(StrEnum):
    FURNITURE = "furniture"
    ARCHITECTURE = "architecture"
    NATURE = "nature"
    CLOTHING = "clothing"
    ANIMAL = "animal"
    VEHICLE = "vehicle"
    WEAPON = "weapon"
    SCREEN_OR_SIGN = "screen_or_sign"
    FOOD = "food"
    OTHER = "other"


class Check(StrEnum):
    UNSCRIPTED_PERSON = auto()
    UNSCRIPTED_OBJECT = auto()
    TEXT_IN_FRAME = auto()
    SETTING = auto()
    MISSING_CHARACTER = auto()
    LIGHT = auto()
    FRAMING = auto()


class Severity(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class Verdict(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    ERROR = "error"


class FrameState(StrEnum):
    RENDERING = auto()
    AUDITING = auto()
    PASSED = auto()
    WARNED = auto()
    WITHHELD = auto()
    FAILED = auto()


@dataclass(frozen=True)
class RenderedFrame:
    shot: tuple[int, int]
    attempt: int
    seed: int
    png: bytes
    width: int
    height: int
    prompt: str


class Renderer(Protocol):
    # width x height: the storyboard's 16:9 size, or a comic panel's rect (comic.md §4 step 6)
    async def render(
        self, shot: Shot, attempt: int, seed: int, width: int, height: int
    ) -> RenderedFrame: ...


@dataclass(frozen=True)
class CheckResult:
    check: Check
    severity: Severity
    ok: bool
    detail: str


@dataclass(frozen=True)
class Audit:
    shot: tuple[int, int]
    attempt: int
    seed: int
    description: FrameDescription | None
    judgement: Judgement | None
    checks: tuple[CheckResult, ...]
    verdict: Verdict
    positions: dict[str, Position]
    models: tuple[str, ...]
    usage: Usage


@dataclass(frozen=True)
class FrameOutcome:
    shot: tuple[int, int]
    state: FrameState
    frame: RenderedFrame | None
    audits: tuple[Audit, ...]
