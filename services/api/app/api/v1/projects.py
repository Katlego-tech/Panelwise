"""POST and GET /api/v1/projects: the upload and the list (web.md §4.1, §6; T053)."""

import asyncio
import logging
import re
import uuid
from pathlib import PurePath
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import ApiError
from app.api.v1.schemas import FrameView, LinesView, Project, ProjectSummary, ShotView
from app.core.auth import Caller, current_caller
from app.frames import ACCEPTED, frame_view, frames_of
from app.projects.codec import load_extraction, load_plan, load_screenplay
from app.projects.job import fail_job, run_job
from app.projects.model import ProjectRow
from app.projects.pipeline import UNEXPECTED
from app.projects.repo import create_upload, get_project, list_summaries, summary
from app.projects.views import entity_views, lines_view, report_view, scene_views, shot_views
from app.storage import AssetStore, StorageError

router = APIRouter()
log = logging.getLogger(__name__)

_FRAMING = 64 * 1024  # multipart boundaries and headers on top of the file itself
_MAX_TITLE_BYTES = 1024
_TITLE_CHARS = 200


def _store(request: Request) -> AssetStore:
    store: AssetStore | None = request.app.state.store
    if store is None:
        raise ApiError(503, "storage_unavailable")
    return store


def _title(typed: object, filename: str | None) -> str:
    text = typed if isinstance(typed, str) else ""
    if len(text.encode()) > _MAX_TITLE_BYTES:
        raise ApiError(413, "too_large")
    # The file name without .pdf (web.md §3); PurePath.stem keeps ".pdf" whole, as a dotfile.
    name = PurePath(filename or "").name
    text = text.strip() or re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE).strip()
    return text[:_TITLE_CHARS].strip() or "Untitled"


def start(request: Request, job_id: uuid.UUID) -> None:
    """Run the job as a background task in this process (web.md §4.1). Without a model it fails
    at once with the unexpected-error copy rather than sitting QUEUED until a restart."""
    state = request.app.state
    if state.model is None:
        log.error("job %s cannot run: NEBIUS_API_KEY is not set", job_id)
        work = fail_job(state.sessions, job_id, UNEXPECTED, None)
    else:
        work = run_job(job_id, sessions=state.sessions, store=state.store, model=state.model)
    task = asyncio.create_task(work)
    state.tasks.add(task)
    task.add_done_callback(state.tasks.discard)


@router.post("/projects", status_code=202)
async def upload(
    request: Request, caller: Annotated[Caller, Depends(current_caller)]
) -> JSONResponse:
    """In web.md §6's order. No UploadFile or Form parameter: FastAPI would read the whole body
    before the caller is checked. So: who (401/503), storage (503), the declared length (411/413),
    then the form, the file's own size (413), the PDF header (400), and only then storage."""
    settings = request.app.state.settings
    store = _store(request)
    length = request.headers.get("content-length")
    if length is None or not length.isdigit():
        raise ApiError(411, "length_required")
    if int(length) > settings.upload_max_bytes + _FRAMING:
        raise ApiError(413, "too_large")
    try:
        form = await request.form(max_files=1, max_fields=1)
    except StarletteHTTPException as exc:  # Starlette's form limits, raised as 400
        raise ApiError(400, "bad_form") from exc
    file = form.get("file")
    if not isinstance(file, UploadFile):  # absent, or sent without a filename (a text field)
        raise ApiError(400, "no_file")
    if file.size is None or file.size > settings.upload_max_bytes:
        raise ApiError(413, "too_large")
    title = _title(form.get("title"), file.filename)
    data = await file.read()
    if not data.startswith(b"%PDF-"):
        raise ApiError(400, "not_a_pdf")

    project_id = uuid.uuid4()
    path = f"scripts/{caller.user_id}/{project_id}.pdf"
    try:
        # Storage first: a row never points at a missing file (a failed insert leaves only an
        # unreferenced one).
        await store.put(path, data, "application/pdf")
    except StorageError as exc:
        raise ApiError(503, "storage_unavailable") from exc
    async with request.app.state.sessions() as session, session.begin():
        project, job = await create_upload(
            session, project_id=project_id, owner=caller.user_id, title=title, pdf_path=path
        )
        made = summary(project, job)
    start(request, job.id)  # after the commit: the job reads what this transaction wrote
    body: dict[str, Any] = {"project": made, "job": made.job}
    return JSONResponse({k: v.model_dump(mode="json") for k, v in body.items()}, status_code=202)


@router.get("/projects")
async def list_projects(
    request: Request, caller: Annotated[Caller, Depends(current_caller)]
) -> list[ProjectSummary]:
    async with request.app.state.sessions() as session:
        return await list_summaries(session, caller.user_id)


# --- the reads (T047; web.md §6 *API internals: the reads and the frames table*) -----------

_SIGNED_URL_S = 3600  # a frame's signed image URL lives an hour


async def _owned(
    request: Request, caller: Caller, project_id: str
) -> tuple[ProjectRow, ProjectSummary]:
    """The caller's project, or 404 -- the same answer for a malformed id, a missing project and
    someone else's, so ids can't be probed. `{id}` is a str parsed here: typed UUID, FastAPI
    would answer a malformed one with its own 422."""
    try:
        pid = uuid.UUID(project_id)
    except ValueError as exc:
        raise ApiError(404, "not_found") from exc
    async with request.app.state.sessions() as session:
        found = await get_project(session, caller.user_id, pid)
    if found is None:
        raise ApiError(404, "not_found")
    return found


@router.get("/projects/{project_id}")
async def read_project(
    request: Request, project_id: str, caller: Annotated[Caller, Depends(current_caller)]
) -> Project:
    row, made = await _owned(request, caller, project_id)
    screenplay = load_screenplay(row.screenplay) if row.screenplay is not None else None
    extraction = load_extraction(row.extraction) if row.extraction is not None else None
    plan = load_plan(row.plan) if row.plan is not None else None
    return Project.model_validate(
        made.model_dump()
        | {
            "scene_list": scene_views(screenplay, plan) if screenplay else None,
            "entities": entity_views(extraction) if extraction else None,
            "report": report_view(extraction, plan) if extraction else None,
        }
    )


@router.get("/projects/{project_id}/lines")
async def read_lines(
    request: Request, project_id: str, caller: Annotated[Caller, Depends(current_caller)]
) -> LinesView:
    row, _ = await _owned(request, caller, project_id)
    if row.screenplay is None:
        raise ApiError(409, "not_ready")
    return lines_view(load_screenplay(row.screenplay))


@router.get("/projects/{project_id}/shots")
async def read_shots(
    request: Request, project_id: str, caller: Annotated[Caller, Depends(current_caller)]
) -> list[ShotView]:
    row, _ = await _owned(request, caller, project_id)
    if row.screenplay is None or row.extraction is None or row.plan is None:
        raise ApiError(409, "not_ready")
    return shot_views(
        load_screenplay(row.screenplay), load_extraction(row.extraction), load_plan(row.plan)
    )


@router.get("/projects/{project_id}/frames")
async def read_frames(
    request: Request, project_id: str, caller: Annotated[Caller, Depends(current_caller)]
) -> list[FrameView]:
    """One FrameView per `frames` row; no rows exist until T021 writes them."""
    row, _ = await _owned(request, caller, project_id)
    async with request.app.state.sessions() as session:
        frames = await frames_of(session, row.id)
    if not frames:
        return []
    if row.screenplay is None:  # frames are written from a plan, which needs a screenplay
        raise ApiError(409, "not_ready")
    screenplay = load_screenplay(row.screenplay)
    store: AssetStore | None = request.app.state.store
    views: list[FrameView] = []
    for frame in frames:
        url: str | None = None
        if frame.state in ACCEPTED and frame.asset is not None:
            if store is None:
                raise ApiError(503, "storage_unavailable")
            try:
                url = await store.signed_url(frame.asset, _SIGNED_URL_S)
            except StorageError as exc:
                raise ApiError(503, "storage_unavailable") from exc
        views.append(frame_view(frame, screenplay, url))
    return views
