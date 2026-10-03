"""Project queries (web.md §6 *API internals*). Functions take a session and never commit."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import Job, ProjectSummary
from app.jobs.model import JobKind, JobRow, JobState
from app.projects.model import ProjectRow


async def create_upload(
    session: AsyncSession, *, project_id: uuid.UUID, owner: uuid.UUID, title: str, pdf_path: str
) -> tuple[ProjectRow, JobRow]:
    """The project and its storyboard job, QUEUED (web.md §4.1). T046 runs the job."""
    project = ProjectRow(id=project_id, owner=owner, title=title, pdf_path=pdf_path)
    job = JobRow(
        id=uuid.uuid4(), project_id=project_id, kind=JobKind.STORYBOARD, state=JobState.QUEUED
    )
    session.add(project)
    await session.flush()  # the project first: the job's foreign key needs it
    session.add(job)
    await session.flush()
    await session.refresh(project)
    await session.refresh(job)
    return project, job


async def list_summaries(session: AsyncSession, owner: uuid.UUID) -> list[ProjectSummary]:
    """The owner's projects, newest first, each with its latest job. `pages`, `scenes` and
    `shots` come from the stage columns (T046), counted in SQL so the list never loads a whole
    screenplay, and are null until their stage has run; `frames` is null until T047/T021 add the
    `frames` table (web.md §6)."""
    pages = ProjectRow.screenplay["page_count"].as_integer()
    scenes = func.jsonb_array_length(ProjectRow.screenplay["scenes"])
    shots = func.jsonb_array_length(ProjectRow.plan["shots"])
    latest = (
        select(JobRow)
        .ext(distinct_on(JobRow.project_id))
        .order_by(JobRow.project_id, JobRow.created_at.desc(), JobRow.id.desc())
        .subquery()
    )
    rows = await session.execute(
        select(ProjectRow, JobRow, pages, scenes, shots)
        .join(latest, latest.c.project_id == ProjectRow.id)
        .join(JobRow, JobRow.id == latest.c.id)
        .where(ProjectRow.owner == owner)
        .order_by(ProjectRow.created_at.desc(), ProjectRow.id.desc())
    )
    return [summary(project, job, pages=p, scenes=sc, shots=sh) for project, job, p, sc, sh in rows]


def summary(
    project: ProjectRow,
    job: JobRow,
    *,
    pages: int | None = None,
    scenes: int | None = None,
    shots: int | None = None,
) -> ProjectSummary:
    return ProjectSummary(
        id=project.id,
        title=project.title,
        created_at=project.created_at,
        pages=pages,
        scenes=scenes,
        shots=shots,
        frames=None,
        # Validated from the row's text: the database's CHECK and Job's Literal agree (web.md §6).
        job=Job.model_validate(
            {
                "id": job.id,
                "state": job.state,
                "stage": job.stage,
                "progress": job.progress,
                "error": job.error,
                "updated_at": job.updated_at,
            }
        ),
    )
