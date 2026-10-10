"""What every renderer backend shares (storyboard.md §6 `render.py`): its error, the record it keeps
of each attempt, and the shape `build_storyboard` needs."""

from dataclasses import dataclass
from typing import Protocol

from app.storyboard.prompt import FramePrompt
from app.storyboard.styles import Style
from app.verify.model import RecordingRenderer

# storyboard.md §6, verbatim: the upload's job, failed at stage rendering by a StoryboardError.
RENDER_STAGE_FAILED = (
    "Shot {shot_id} couldn't be drawn, so the storyboard stopped. Upload the script again to try "
    "once more: drawings already made aren't drawn twice."
)
# The same, when the renderer's cause was RenderQuotaExceeded (§3.5).
RENDER_BUDGET_SPENT = (
    "Today's free drawing budget ran out at shot {shot_id}, so the storyboard stopped. It resets "
    "at 00:00 UTC: upload the script again after that, and drawings already made aren't drawn "
    "twice."
)


class RendererError(RuntimeError):
    """A drawing couldn't be made: the backend refused, failed or timed out. Its message names the
    status and model, never a key or a prompt."""


class RenderQuotaExceeded(RendererError):
    """Workers AI's free neurons for the day are used (3036); they reset at 00:00 UTC (§3.5)."""


@dataclass(frozen=True)
class RenderRecord:
    """One attempt as the renderer stored it (§3.3): `asset` is its Storage path."""

    shot: tuple[int, int]
    attempt: int
    key: str
    asset: str
    prompt: FramePrompt
    cached: bool
    seconds: float | None
    neurons: float | None = None  # Workers AI's cf-ai-neurons; None for a store hit


class RenderRecorder(RecordingRenderer, Protocol):
    """A RecordingRenderer whose records are RenderRecords, in one style: build_storyboard's."""

    style: Style

    def record(self, shot: tuple[int, int], attempt: int) -> RenderRecord: ...
