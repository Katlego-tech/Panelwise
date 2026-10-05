"""Job queries (web.md §6 *API internals*). Functions take a session and never commit."""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.model import RESTARTED, JobRow, JobState


async def fail_interrupted(session: AsyncSession) -> int:
    """The restart sweep (web.md §4.1): every QUEUED or RUNNING job becomes FAILED with the
    restart message, its stage kept. Returns how many. A retry is a new job (deploy.md §5)."""
    result = await session.execute(
        update(JobRow)
        .where(JobRow.state.in_([JobState.QUEUED, JobState.RUNNING]))
        .values(state=JobState.FAILED, error=RESTARTED)
    )
    return result.rowcount  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
