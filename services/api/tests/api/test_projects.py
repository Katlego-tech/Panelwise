"""POST and GET /api/v1/projects -- web.md §6 (rows marked T053, *API internals*). A fake token
verifier and an in-memory AssetStore; the real test Postgres."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth import AuthError, Caller
from app.core.config import Settings
from app.jobs import JobRow
from app.main import create_app
from app.projects.model import ProjectRow

pytestmark = pytest.mark.db

PDF = b"%PDF-1.7\n" + b"x" * 200
LIMIT = 1_000  # upload_max_bytes in these tests


class FakeVerifier:
    """Token "user-<uuid>" is that user; anything else is refused."""

    async def verify(self, token: str) -> Caller:
        if not token.startswith("user-"):
            raise AuthError("bad")
        return Caller(user_id=uuid.UUID(token.removeprefix("user-")))


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def exists(self, path: str) -> bool:
        return path in self.objects

    async def get(self, path: str) -> bytes:
        return self.objects[path][0]

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        self.objects.setdefault(path, (data, content_type))

    async def signed_url(self, path: str, expires_in_s: int) -> str:
        return f"https://signed/{path}?e={expires_in_s}"


ME, SOMEONE = uuid.uuid4(), uuid.uuid4()


def auth(user: uuid.UUID = ME) -> dict[str, str]:
    return {"Authorization": f"Bearer user-{user}"}


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def client(
    migrated: str, store: MemoryStore, sessions: async_sessionmaker[AsyncSession]
) -> Iterator[TestClient]:
    # `sessions` empties the tables first.
    settings = Settings(database_url=migrated, upload_max_bytes=LIMIT)
    with TestClient(create_app(settings, verifier=FakeVerifier(), store=store)) as c:
        yield c


def upload(c: TestClient, data: bytes = PDF, name: str = "The Red Kite.pdf", **kw: object):
    files = {"file": (name, data, "application/pdf")}
    return c.post("/api/v1/projects", files=files, headers=kw.pop("headers", auth()), **kw)  # type: ignore[arg-type]


# --- refusals, each before anything is stored ----------------------------------------


def test_no_token_or_a_bad_one_is_401(client: TestClient, store: MemoryStore) -> None:
    for headers in ({}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic x"}):
        res = upload(client, headers=headers)
        assert (res.status_code, res.json()) == (401, {"error": "unauthorized"})
        assert res.headers["www-authenticate"] == "Bearer"
    assert client.get("/api/v1/projects").status_code == 401
    assert store.objects == {}


def test_a_body_without_a_length_is_411(client: TestClient) -> None:
    res = client.post(
        "/api/v1/projects",
        content=iter([b"--x\r\n"]),  # streamed: no Content-Length
        headers=auth() | {"Content-Type": "multipart/form-data; boundary=x"},
    )
    assert (res.status_code, res.json()) == (411, {"error": "length_required"})


def test_an_oversized_body_is_413_from_its_length_alone(
    client: TestClient, store: MemoryStore
) -> None:
    res = upload(client, data=PDF + b"x" * (LIMIT + 70_000))
    assert (res.status_code, res.json()) == (413, {"error": "too_large"})
    assert store.objects == {}


def test_a_file_one_byte_over_inside_an_allowed_length_is_413(
    client: TestClient, store: MemoryStore
) -> None:
    res = upload(client, data=PDF + b"x" * (LIMIT + 1 - len(PDF)))
    assert (res.status_code, res.json()) == (413, {"error": "too_large"})
    assert store.objects == {}


def test_a_title_over_1_kib_is_413(client: TestClient) -> None:
    res = client.post(
        "/api/v1/projects",
        files={"file": ("a.pdf", PDF, "application/pdf")},
        data={"title": "t" * 1025},
        headers=auth(),
    )
    assert (res.status_code, res.json()) == (413, {"error": "too_large"})


def test_no_file_or_a_text_file_field_is_no_file(client: TestClient) -> None:
    res = client.post("/api/v1/projects", data={"title": "t"}, headers=auth())
    assert (res.status_code, res.json()) == (400, {"error": "no_file"})
    # A "file" part sent without a filename is a text field to Starlette, not a file.
    res = client.post("/api/v1/projects", data={"file": "%PDF-1.7"}, headers=auth())
    assert (res.status_code, res.json()) == (400, {"error": "no_file"})


def test_two_files_are_a_bad_form(client: TestClient) -> None:
    files = [
        ("file", ("a.pdf", PDF, "application/pdf")),
        ("extra", ("b.pdf", PDF, "application/pdf")),
    ]
    res = client.post("/api/v1/projects", files=files, headers=auth())
    assert (res.status_code, res.json()) == (400, {"error": "bad_form"})


def test_a_file_that_is_not_a_pdf_is_400(client: TestClient, store: MemoryStore) -> None:
    res = upload(client, data=b"GIF89a....", name="kite.pdf")
    assert (res.status_code, res.json()) == (400, {"error": "not_a_pdf"})
    assert store.objects == {}


def test_no_storage_or_no_verifier_is_503_before_the_body(migrated: str) -> None:
    settings = Settings(database_url=migrated, upload_max_bytes=LIMIT)
    with TestClient(create_app(settings, verifier=FakeVerifier(), store=None)) as c:
        res = upload(c, data=b"not even a pdf")
        assert (res.status_code, res.json()) == (503, {"error": "storage_unavailable"})
    with TestClient(create_app(settings, verifier=None, store=MemoryStore())) as c:
        res = upload(c)
        assert (res.status_code, res.json()) == (503, {"error": "auth_unavailable"})


# --- the upload and the list ----------------------------------------------------------


async def test_an_upload_stores_the_pdf_and_queues_a_job(
    client: TestClient, store: MemoryStore, sessions: async_sessionmaker[AsyncSession]
) -> None:
    res = upload(client)
    assert res.status_code == 202
    body = res.json()
    project, job = body["project"], body["job"]
    assert project["title"] == "The Red Kite"  # the file name without .pdf
    assert (project["pages"], project["scenes"], project["shots"], project["frames"]) == (None,) * 4
    assert (job["state"], job["stage"], job["progress"], job["error"]) == ("queued", None, 0, None)
    assert project["job"] == job
    path = f"scripts/{ME}/{project['id']}.pdf"
    assert store.objects == {path: (PDF, "application/pdf")}
    async with sessions() as s:
        row = await s.get(ProjectRow, uuid.UUID(project["id"]))
        jobs = (await s.execute(select(JobRow))).scalars().all()
    assert row is not None and (row.owner, row.pdf_path) == (ME, path)
    assert [str(j.id) for j in jobs] == [job["id"]]


def test_a_typed_title_wins_and_is_trimmed_to_200(client: TestClient) -> None:
    res = client.post(
        "/api/v1/projects",
        files={"file": ("x.pdf", PDF, "application/pdf")},
        data={"title": "  " + "T" * 300 + "  "},
        headers=auth(),
    )
    assert res.status_code == 202 and res.json()["project"]["title"] == "T" * 200
    res = client.post(
        "/api/v1/projects",
        files={"file": (".pdf", PDF, "application/pdf")},
        data={"title": "   "},
        headers=auth(),
    )
    assert res.json()["project"]["title"] == "Untitled"


def test_the_list_is_only_the_callers_newest_first(client: TestClient) -> None:
    first = upload(client, name="First.pdf").json()["project"]["id"]
    upload(client, name="Theirs.pdf", headers=auth(SOMEONE))
    second = upload(client, name="Second.pdf").json()["project"]["id"]
    res = client.get("/api/v1/projects", headers=auth())
    assert res.status_code == 200
    assert [p["id"] for p in res.json()] == [second, first]
    theirs = client.get("/api/v1/projects", headers=auth(SOMEONE)).json()
    assert [p["title"] for p in theirs] == ["Theirs"]
    assert client.get("/api/v1/projects", headers=auth(uuid.uuid4())).json() == []
