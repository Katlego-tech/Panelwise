"""The upload's job: run the pipeline and write what it reports (web.md §3, §4.1, §6; T046).

Each stage's column and the job's advance are one transaction, so a page never sees a stage's
result without the job saying it is there, nor the other way round. A failure the user can act
on carries §4.1's copy (`PipelineError`); anything else is a bug: logged with its traceback, and
the job says only "something went wrong on our side". `run_job` never raises (it runs as a
background task); a cancelled one stays RUNNING for the next start's sweep.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.grounding import Extraction
from app.jobs import JobRow, JobState
from app.llm import NebiusChatModel
from app.projects.codec import dump_extraction, dump_plan, dump_screenplay
from app.projects.model import ProjectRow
from app.projects.pipeline import UNEXPECTED, PipelineError, Stage, StageResult, run_pipeline
from app.script import Screenplay
from app.storage import AssetStore

log = logging.getLogger(__name__)


def _column(finished: StageResult | None) -> tuple[str | None, dict[str, Any] | None]:
    """The stage column a finished stage's result goes in (web.md §6's on_advance table)."""
    if isinstance(finished, Screenplay):
        return "screenplay", dump_screenplay(finished)
    if isinstance(finished, Extraction):
        return "extraction", dump_extraction(finished)
    return None, None


async def advance(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    project_id: uuid.UUID,
    stage: Stage,
    progress: int,
    column: str | None,
    value: dict[str, Any] | None,
    state: JobState = JobState.RUNNING,
) -> None:
    """One step: the stage's column (if any) and the job's state, stage and progress. The caller
    holds the transaction."""
    if column is not None:
        await session.execute(
            update(ProjectRow).where(ProjectRow.id == project_id).values({column: value})
        )
    await session.execute(
        update(JobRow)
        .where(JobRow.id == job_id)
        .values(state=state, stage=stage, progress=progress)
    )


async def fail_job(
    sessions: async_sessionmaker[AsyncSession], job_id: uuid.UUID, error: str, stage: Stage | None
) -> None:
    values: dict[str, Any] = {"state": JobState.FAILED, "error": error}
    if stage is not None:
        values["stage"] = stage
    try:
        async with sessions() as session, session.begin():
            await session.execute(update(JobRow).where(JobRow.id == job_id).values(values))
    except Exception:
        log.exception("job %s: could not record its failure", job_id)


async def run_job(
    job_id: uuid.UUID,
    *,
    sessions: async_sessionmaker[AsyncSession],
    store: AssetStore,
    model: NebiusChatModel,
) -> None:
    try:
        async with sessions() as session:
            job = await session.get(JobRow, job_id)
            project = await session.get(ProjectRow, job.project_id) if job else None
        if job is None or project is None:
            raise LookupError(f"job {job_id} or its project is gone")
        project_id = project.id
        pdf = await store.get(project.pdf_path)

        async def on_advance(stage: Stage, progress: int, finished: StageResult | None) -> None:
            column, value = _column(finished)
            async with sessions() as session, session.begin():
                await advance(
                    session,
                    job_id=job_id,
                    project_id=project_id,
                    stage=stage,
                    progress=progress,
                    column=column,
                    value=value,
                )

        result = await run_pipeline(pdf, model, on_advance=on_advance)
        async with sessions() as session, session.begin():
            await advance(
                session,
                job_id=job_id,
                project_id=project_id,
                stage=Stage.PLANNING,
                progress=60,
                column="plan",
                value=dump_plan(result.plan),
                state=JobState.DONE,
            )
    except PipelineError as error:
        await fail_job(sessions, job_id, error.message, error.stage)
    except Exception:
        log.exception("job %s failed unexpectedly", job_id)
        await fail_job(sessions, job_id, UNEXPECTED, None)
