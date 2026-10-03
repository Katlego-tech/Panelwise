"""The read endpoints and frames: web.md §6 (rows marked T047, *API internals: the reads*)."""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.frames.model import FrameRow
from app.main import create_app
from app.projects.codec import load_extraction, load_plan, load_screenplay
from app.projects.job import run_job
from app.projects.model import ProjectRow
from app.projects.repo import create_upload
from app.projects.views import entity_views, lines_view, report_view, scene_views, shot_views
from tests.fakes import FakeVerifier, MemoryStore
from tests.projects.test_pipeline import GOOD_PDF, Models, make

pytestmark = pytest.mark.db

ME, SOMEONE = uuid.uuid4(), uuid.uuid4()


def auth(user: uuid.UUID = ME) -> dict[str, str]:
    return {"Authorization": f"Bearer user-{user}"}


async def project(
    sessions: async_sessionmaker[AsyncSession], store: MemoryStore, *, run: bool
) -> tuple[uuid.UUID, uuid.UUID]:
    pid = uuid.uuid4()
    path = f"scripts/{ME}/{pid}.pdf"
    await store.put(path, GOOD_PDF, "application/pdf")
    async with sessions() as s, s.begin():
        _, job = await create_upload(s, project_id=pid, owner=ME, title="Lighthouse", pdf_path=path)
    if run:
        await run_job(job.id, sessions=sessions, store=store, model=make(Models()))
    return pid, job.id


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def client(
    migrated: str, store: MemoryStore, sessions: async_sessionmaker[AsyncSession]
) -> Iterator[TestClient]:
    app = create_app(Settings(database_url=migrated), verifier=FakeVerifier(), store=store)
    with TestClient(app) as c:
        yield c


def get(c: TestClient, path: str, user: uuid.UUID = ME) -> tuple[int, Any]:
    res = c.get(f"/api/v1/projects{path}", headers=auth(user))
    return res.status_code, res.json()


async def test_a_planned_project_reads_as_the_builders_make_it(
    client: TestClient, store: MemoryStore, sessions: async_sessionmaker[AsyncSession]
) -> None:
    pid, _ = await project(sessions, store, run=True)
    async with sessions() as s:
        row = await s.get(ProjectRow, pid)
    assert row is not None
    screenplay, extraction, plan = (
        load_screenplay(row.screenplay),
        load_extraction(row.extraction),
        load_plan(row.plan),
    )

    status, body = get(client, f"/{pid}")
    assert status == 200
    assert body["scene_list"] == [v.model_dump(mode="json") for v in scene_views(screenplay, plan)]
    assert body["entities"] == [v.model_dump(mode="json") for v in entity_views(extraction)]
    assert body["report"] == report_view(extraction, plan).model_dump(mode="json")
    assert (body["pages"], body["scenes"], body["shots"], body["frames"]) == (
        screenplay.page_count,
        len(screenplay.scenes),
        len(plan.shots),
        None,
    )
    assert body["job"]["state"] == "done"

    assert get(client, f"/{pid}/lines") == (200, lines_view(screenplay).model_dump(mode="json"))
    expected = [v.model_dump(mode="json") for v in shot_views(screenplay, extraction, plan)]
    assert get(client, f"/{pid}/shots") == (200, expected)
    assert get(client, f"/{pid}/frames") == (200, [])  # no rows until T021 writes them


async def test_before_it_runs_the_parts_are_null_and_the_pages_not_ready(
    client: TestClient, store: MemoryStore, sessions: async_sessionmaker[AsyncSession]
) -> None:
    pid, _ = await project(sessions, store, run=False)
    status, body = get(client, f"/{pid}")
    assert status == 200
    assert (body["scene_list"], body["entities"], body["report"]) == (None, None, None)
    assert get(client, f"/{pid}/lines") == (409, {"error": "not_ready"})
    assert get(client, f"/{pid}/shots") == (409, {"error": "not_ready"})


async def test_someone_elses_or_a_missing_or_a_malformed_id_is_the_same_404(
    client: TestClient, store: MemoryStore, sessions: async_sessionmaker[AsyncSession]
) -> None:
    pid, _ = await project(sessions, store, run=True)
    for path in ("", "/lines", "/shots", "/frames"):
        assert get(client, f"/{pid}{path}", user=SOMEONE) == (404, {"error": "not_found"})
        assert get(client, f"/{uuid.uuid4()}{path}") == (404, {"error": "not_found"})
        assert get(client, f"/not-a-uuid{path}") == (404, {"error": "not_found"})
    assert client.get(f"/api/v1/projects/{pid}").status_code == 401  # no token


async def test_frames_come_only_from_rows_and_images_only_when_accepted(
    client: TestClient, store: MemoryStore, sessions: async_sessionmaker[AsyncSession]
) -> None:
    pid, jid = await project(sessions, store, run=True)
    states = [
        ("passed", "frames/a.png"),
        ("warned", "frames/b.png"),
        ("withheld", None),
        ("rendering", None),
        ("auditing", None),
        ("failed", None),
    ]
    async with sessions() as s, s.begin():
        for n, (state, asset) in enumerate(states, 1):
            s.add(
                FrameRow(
                    project_id=pid,
                    scene_index=0,
                    shot_number=n,
                    state=state,
                    attempt=1,
                    job_id=jid,
                    asset=asset,
                    withheld_check="unscripted_person" if state == "withheld" else None,
                )
            )
    status, frames = get(client, f"/{pid}/frames")
    assert status == 200
    assert [f["state"] for f in frames] == [s for s, _ in states]
    assert [f["image_url"] for f in frames] == [
        "https://signed/frames/a.png?e=3600",
        "https://signed/frames/b.png?e=3600",
        None,
        None,
        None,
        None,
    ]
    status, body = get(client, f"/{pid}")
    # total is the plan's shot count, not the rows: most shots have no row yet (web.md §6).
    assert body["frames"] == {"settled": 4, "total": body["shots"], "withheld": 1, "active": 2}
    assert body["frames"]["total"] != len(states)  # the plan's shots, not the rows
    (summary,) = client.get("/api/v1/projects", headers=auth()).json()
    assert summary["frames"] == body["frames"]


async def test_the_database_keeps_an_asset_off_a_frame_that_isnt_accepted(
    store: MemoryStore, sessions: async_sessionmaker[AsyncSession]
) -> None:
    from sqlalchemy.exc import IntegrityError

    pid, jid = await project(sessions, store, run=False)
    with pytest.raises(IntegrityError):
        async with sessions() as s, s.begin():
            s.add(
                FrameRow(
                    project_id=pid,
                    scene_index=0,
                    shot_number=1,
                    state="withheld",
                    attempt=1,
                    job_id=jid,
                    asset="frames/leak.png",
                )
            )


async def test_a_users_extra_render_never_reads_attempt_4_of_3(
    client: TestClient, store: MemoryStore, sessions: async_sessionmaker[AsyncSession]
) -> None:
    pid, jid = await project(sessions, store, run=True)
    async with sessions() as s, s.begin():
        s.add(
            FrameRow(
                project_id=pid,
                scene_index=0,
                shot_number=1,
                state="rendering",
                attempt=4,
                job_id=jid,
            )
        )
    (frame,) = get(client, f"/{pid}/frames")[1]
    assert (frame["attempt"], frame["max_renders"]) == (4, 4)
