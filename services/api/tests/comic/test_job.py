"""T064: the comic job (comic.md §4a, §9 The comic job). A real Postgres, the sketch renderer (it
draws at any size and records before returning), a scripted audit, an in-memory store."""

import asyncio
import hashlib
import io
import uuid
from dataclasses import replace
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.comic import job as comic_job
from app.comic.job import (
    COMIC_LAYOUT_FAILED,
    COMIC_LAYOUT_FAILED_ANY,
    COMIC_RENDER_FAILED,
    COMIC_UNEXPECTED,
    ComicRefused,
    run_comic_job,
    start_comic,
)
from app.comic.layout import layout_geometry
from app.comic.model import ComicError
from app.comic.rows import ComicRow
from app.frames.check import SketchRenderer
from app.frames.model import FrameAuditRow, FrameRow
from app.frames.repo import audits_of
from app.jobs import JobKind, JobRow, JobState
from app.projects.codec import load_plan, load_screenplay
from app.projects.model import ProjectRow
from app.shots import Shot
from app.verify import loop
from app.verify.audit import seed_for
from app.verify.model import Audit, Check, RenderedFrame, Verdict
from tests.api.test_read import ME, SOMEONE, project
from tests.conftest import API
from tests.fakes import MemoryStore
from tests.frames.test_t021 import audit
from tests.projects.test_pipeline import Models, make

pytestmark = pytest.mark.db

type Key = tuple[int, int]


class Sizes(SketchRenderer):
    """The sketch renderer, remembering every size it was asked for, in order."""

    def __init__(self, store: MemoryStore) -> None:
        super().__init__(store)
        self.asked: list[tuple[Key, int, int, int]] = []

    async def render(
        self, shot: Shot, attempt: int, seed: int, width: int, height: int
    ) -> RenderedFrame:
        self.asked.append(((shot.scene_index, shot.number), attempt, width, height))
        return await super().render(shot, attempt, seed, width, height)


class Script:
    """The audit's answers: each panel's next scripted verdict (PASS when none is left); every
    call recorded as (panel, attempt, seed)."""

    def __init__(self) -> None:
        self.verdicts: dict[Key, list[Verdict]] = {}
        self.calls: list[tuple[Key, int, int]] = []


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch) -> Script:
    script = Script()

    async def fake(
        model: Any, frame: RenderedFrame, shot: Shot, screenplay: Any, extraction: Any
    ) -> Audit:
        script.calls.append((frame.shot, frame.attempt, frame.seed))
        queue = script.verdicts.get(frame.shot, [])
        verdict = queue.pop(0) if queue else Verdict.PASS
        failed = (Check.UNSCRIPTED_PERSON,) if verdict is Verdict.FAIL else ()
        return replace(audit(frame.attempt, verdict, *failed), shot=frame.shot, seed=frame.seed)

    monkeypatch.setattr(loop, "audit_frame", fake)
    return script


async def planned(sessions: async_sessionmaker[AsyncSession], store: MemoryStore) -> ProjectRow:
    pid, _ = await project(sessions, store, run=True)
    async with sessions() as s:
        row = await s.get(ProjectRow, pid)
    assert row is not None
    return row


async def make_comic(
    sessions: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    pid: uuid.UUID,
    renderer: SketchRenderer | None = None,
) -> JobRow:
    async with sessions() as s, s.begin():
        started = await start_comic(s, pid, ME, renderer=True, store=True)
    drawn = renderer or SketchRenderer(store)
    await run_comic_job(
        started.id,
        sessions=sessions,
        store=store,
        model=make(Models()),
        factory=lambda screenplay, extraction: drawn,
    )
    async with sessions() as s:
        done = await s.get(JobRow, started.id)
    assert done is not None
    return done


async def comic_audits(sessions: async_sessionmaker[AsyncSession]) -> list[FrameAuditRow]:
    async with sessions() as s:
        rows = await s.scalars(
            select(FrameAuditRow).order_by(
                FrameAuditRow.scene_index, FrameAuditRow.shot_number, FrameAuditRow.attempt
            )
        )
        return list(rows)


# --- a comic, end to end ----------------------------------------------------------------------


async def test_every_panel_is_drawn_at_its_rect_audited_as_comic_and_stored_by_content(
    sessions: async_sessionmaker[AsyncSession],
    scripted: Script,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    row = await planned(sessions, store)
    plan, screenplay = load_plan(row.plan), load_screenplay(row.screenplay)  # type: ignore[arg-type]
    book = layout_geometry(plan, screenplay)
    rects = {(p.scene_index, p.shot_number): p.rect for pg in book.pages for p in pg.panels}
    first = (plan.shots[0].scene_index, plan.shots[0].number)
    scripted.verdicts[first] = [Verdict.FAIL, Verdict.FAIL, Verdict.FAIL]  # withheld; the rest pass
    progress: list[int] = []
    real_progress = comic_job._progress  # pyright: ignore[reportPrivateUsage]

    async def watch(sessions: Any, job_id: uuid.UUID, value: int) -> None:
        progress.append(value)
        await real_progress(sessions, job_id, value)

    monkeypatch.setattr(comic_job, "_progress", watch)
    renderer = Sizes(store)

    job = await make_comic(sessions, store, row.id, renderer)

    assert (job.kind, job.state, job.progress, job.error) == (JobKind.COMIC, "done", 100, None)
    # Every request at exactly its panel's rect, panels in plan order, three tries for the first.
    keys = [(s.scene_index, s.number) for s in plan.shots]
    assert [k for k, *_ in renderer.asked] == [first, first, first, *keys[1:]]
    assert all((w, h) == rects[k][2:] for k, _, w, h in renderer.asked)
    assert progress == sorted(progress) and progress[-1] == 90 and len(progress) == len(keys)
    # Logged as the comic's, never a frames row, and the storyboard's audit log doesn't see them.
    logged = await comic_audits(sessions)
    assert {a.target for a in logged} == {"comic"} and len(logged) == len(renderer.asked)
    async with sessions() as s:
        assert await s.scalar(select(func.count()).select_from(FrameRow)) == 0
        assert await audits_of(s, row.id) == {}
        comic = await s.get(ComicRow, row.id)
    assert comic is not None and comic.job_id == job.id
    # Pages and PDF at their content hashes; frame_url a Storage path, none for the withheld panel.
    for path in [*comic.pages, comic.pdf]:
        data, _ = store.objects[path]
        assert path.startswith("comics/") and hashlib.sha256(data).hexdigest() in path
    panels = {tuple(p["shot"]): p for pg in comic.layout["pages"] for p in pg["panels"]}
    assert panels[first]["withheld"] and "frame_url" not in panels[first]
    for key in keys[1:]:
        assert not panels[key]["withheld"] and panels[key]["frame_url"] in store.objects
    page = Image.open(io.BytesIO(store.objects[comic.pages[0]][0]))
    assert page.size == (1988, 3075)


async def test_a_second_job_reuses_accepted_panels_and_numbers_new_attempts_after_the_last(
    sessions: async_sessionmaker[AsyncSession], scripted: Script
) -> None:
    store = MemoryStore()
    row = await planned(sessions, store)
    plan = load_plan(row.plan)  # type: ignore[arg-type]
    first = (plan.shots[0].scene_index, plan.shots[0].number)
    scripted.verdicts[first] = [Verdict.FAIL, Verdict.FAIL, Verdict.FAIL]
    one = await make_comic(sessions, store, row.id)
    before = len(scripted.calls)
    renderer = Sizes(store)

    two = await make_comic(sessions, store, row.id, renderer)

    assert (one.state, two.state) == ("done", "done")
    # Only the withheld panel is drawn and audited again, at attempt 4 with attempt 4's seed.
    assert [(k, a) for k, a, *_ in renderer.asked] == [(first, 4)]
    assert scripted.calls[before:] == [(first, 4, seed_for(plan.shots[0], 4))]
    async with sessions() as s:
        comic = await s.get(ComicRow, row.id)
    assert comic is not None and comic.job_id == two.id
    assert all(not p["withheld"] for pg in comic.layout["pages"] for p in pg["panels"])


# --- failures ---------------------------------------------------------------------------------


async def test_a_renderer_error_fails_the_job_and_keeps_the_previous_comic(
    sessions: async_sessionmaker[AsyncSession], scripted: Script
) -> None:
    store = MemoryStore()
    row = await planned(sessions, store)
    plan = load_plan(row.plan)  # type: ignore[arg-type]
    first = (plan.shots[0].scene_index, plan.shots[0].number)
    scripted.verdicts[first] = [Verdict.FAIL, Verdict.FAIL, Verdict.FAIL]
    one = await make_comic(sessions, store, row.id)

    class Broken(SketchRenderer):
        async def render(
            self, shot: Shot, attempt: int, seed: int, width: int, height: int
        ) -> RenderedFrame:
            raise RuntimeError("the pencil broke")

    two = await make_comic(sessions, store, row.id, Broken(store))
    assert (two.state, two.error) == ("failed", COMIC_RENDER_FAILED)
    async with sessions() as s:
        comic = await s.get(ComicRow, row.id)
    assert comic is not None and comic.job_id == one.id


async def test_a_panel_drawn_at_the_wrong_size_fails_at_once(
    sessions: async_sessionmaker[AsyncSession], scripted: Script
) -> None:
    store = MemoryStore()
    row = await planned(sessions, store)

    class Ignores(Sizes):
        async def render(
            self, shot: Shot, attempt: int, seed: int, width: int, height: int
        ) -> RenderedFrame:
            return await super().render(shot, attempt, seed, 1280, 720)

    renderer = Ignores(store)
    job = await make_comic(sessions, store, row.id, renderer)
    assert (job.state, job.error) == ("failed", COMIC_RENDER_FAILED)
    assert len(renderer.asked) == 1  # stopped at the first panel, not after every other


async def test_an_audit_error_is_unexpected_not_a_renderer_failure(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore()
    row = await planned(sessions, store)

    async def down(*_: Any) -> Audit:
        raise RuntimeError("the judge is down")

    monkeypatch.setattr(loop, "audit_frame", down)
    job = await make_comic(sessions, store, row.id)
    assert (job.state, job.error) == ("failed", COMIC_UNEXPECTED)


async def test_a_lettering_failure_names_the_shot_as_the_web_does(
    sessions: async_sessionmaker[AsyncSession],
    scripted: Script,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    row = await planned(sessions, store)
    screenplay = load_screenplay(row.screenplay)  # type: ignore[arg-type]

    def no_room(*_: Any) -> Any:
        raise ComicError("scene 1, shot 1: no room", shot=(1, 1))

    monkeypatch.setattr(comic_job, "place_lettering", no_room)
    job = await make_comic(sessions, store, row.id)
    shot_id = f"{screenplay.scenes[1].number}.1"
    assert (job.state, job.error) == ("failed", COMIC_LAYOUT_FAILED.format(shot_id=shot_id))

    def nameless(*_: Any) -> Any:
        raise ComicError("no shot named")

    monkeypatch.setattr(comic_job, "place_lettering", nameless)
    job = await make_comic(sessions, store, row.id)
    assert job.error == COMIC_LAYOUT_FAILED_ANY


def test_a_shot_outside_the_screenplay_falls_back_to_the_message_that_names_none() -> None:
    error = ComicError("scene 99", shot=(99, 1))
    assert comic_job._layout_message(error, None) == COMIC_LAYOUT_FAILED_ANY  # pyright: ignore[reportPrivateUsage]


# --- start_comic: the checks in order, nothing written ----------------------------------------


async def comic_jobs(sessions: async_sessionmaker[AsyncSession]) -> int:
    async with sessions() as s:
        found = await s.scalar(
            select(func.count()).select_from(JobRow).where(JobRow.kind == JobKind.COMIC)
        )
    return found or 0


async def refused(
    sessions: async_sessionmaker[AsyncSession],
    pid: uuid.UUID,
    owner: uuid.UUID = ME,
    *,
    renderer: bool = True,
    store: bool = True,
) -> str:
    with pytest.raises(ComicRefused) as caught:
        async with sessions() as s, s.begin():
            await start_comic(s, pid, owner, renderer=renderer, store=store)
    return caught.value.code


async def test_start_comic_answers_each_check_in_order_and_writes_nothing(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    store = MemoryStore()
    row = await planned(sessions, store)
    unplanned, _ = await project(sessions, store, run=False)
    assert await refused(sessions, uuid.uuid4()) == "not_found"
    assert await refused(sessions, row.id, SOMEONE) == "not_found"
    assert await refused(sessions, unplanned, renderer=False, store=False) == "not_ready"
    assert await refused(sessions, row.id, renderer=False, store=False) == "renderer_unavailable"
    assert await refused(sessions, row.id, store=False) == "storage_unavailable"
    assert await comic_jobs(sessions) == 0
    async with sessions() as s, s.begin():
        s.add(
            JobRow(id=uuid.uuid4(), project_id=row.id, kind=JobKind.COMIC, state=JobState.RUNNING)
        )
    assert await refused(sessions, row.id, renderer=False) == "comic_running"


async def test_two_clicks_at_once_make_one_job(sessions: async_sessionmaker[AsyncSession]) -> None:
    store = MemoryStore()
    row = await planned(sessions, store)

    async def click() -> str:
        try:
            async with sessions() as s, s.begin():
                await start_comic(s, row.id, ME, renderer=True, store=True)
                await asyncio.sleep(0.05)  # hold the lock while the other click waits on it
        except ComicRefused as refusal:
            return refusal.code
        return "started"

    assert sorted(await asyncio.gather(click(), click())) == ["comic_running", "started"]
    assert await comic_jobs(sessions) == 1


# --- the migration ------------------------------------------------------------------------------


async def test_the_migration_downgrades_with_comics_present(
    sessions: async_sessionmaker[AsyncSession],
    migrated: str,
    scripted: Script,
) -> None:
    store = MemoryStore()
    row = await planned(sessions, store)
    await make_comic(sessions, store, row.id)
    config = Config(str(API / "alembic.ini"))
    config.set_main_option("script_location", str(API / "migrations"))
    config.attributes["database_url"] = migrated
    await asyncio.to_thread(command.downgrade, config, "0004")
    try:
        async with sessions() as s:
            assert await s.scalar(text("SELECT to_regclass('public.comics')")) is None
            assert await s.scalar(text("SELECT count(*) FROM jobs WHERE kind = 'comic'")) == 0
    finally:
        await asyncio.to_thread(command.upgrade, config, "head")
    async with sessions() as s:
        assert await s.scalar(select(func.count()).select_from(FrameAuditRow)) == 0
