"""SupabaseStore against Supabase Storage's REST API, as it answered on 2026-10-02 (T053;
storyboard.md §6). No network: httpx2.MockTransport replays those answers."""

import json

import httpx2
import pytest

from app.storage import AssetNotFound, StorageError, SupabaseStore

URL = "https://example.supabase.co"
OBJ = f"{URL}/storage/v1/object/panelwise-dev"
DUPLICATE = {"statusCode": "409", "error": "Duplicate", "message": "The resource already exists"}
MISSING = {"statusCode": "404", "error": "not_found", "message": "Object not found"}


def store(handler: httpx2.MockTransport) -> SupabaseStore:
    client = httpx2.AsyncClient(transport=handler)
    return SupabaseStore(url=URL, secret_key="sb_secret_x", bucket="panelwise-dev", client=client)


def requests_to(*answers: httpx2.Response) -> tuple[httpx2.MockTransport, list[httpx2.Request]]:
    seen: list[httpx2.Request] = []
    queue = list(answers)

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return queue.pop(0)

    return httpx2.MockTransport(handler), seen


async def test_put_uploads_without_upsert_using_the_secret_key() -> None:
    transport, seen = requests_to(httpx2.Response(200, json={"Key": "k"}))
    await store(transport).put("scripts/u/p.pdf", b"%PDF-1.7", "application/pdf")
    (req,) = seen
    assert (req.method, str(req.url)) == ("POST", f"{OBJ}/scripts/u/p.pdf")
    assert req.headers["authorization"] == "Bearer sb_secret_x"
    assert req.headers["apikey"] == "sb_secret_x"
    assert req.headers["x-upsert"] == "false"
    assert req.headers["content-type"] == "application/pdf"
    assert req.read() == b"%PDF-1.7"


@pytest.mark.parametrize(
    "answer", [httpx2.Response(400, json=DUPLICATE), httpx2.Response(409, json=DUPLICATE)]
)
async def test_put_of_an_existing_path_is_a_success(answer: httpx2.Response) -> None:
    transport, _ = requests_to(answer)
    await store(transport).put("a.png", b"x", "image/png")  # idempotent: no error


async def test_put_failing_otherwise_raises() -> None:
    transport, _ = requests_to(httpx2.Response(500, json={"message": "boom"}))
    with pytest.raises(StorageError):
        await store(transport).put("a.png", b"x", "image/png")


async def test_get_returns_the_bytes_and_a_missing_object_is_not_found() -> None:
    transport, seen = requests_to(
        httpx2.Response(200, content=b"one"), httpx2.Response(400, json=MISSING)
    )
    s = store(transport)
    assert await s.get("scripts/u/p.pdf") == b"one"
    with pytest.raises(AssetNotFound):
        await s.get("scripts/u/missing.pdf")
    assert [r.method for r in seen] == ["GET", "GET"]


async def test_exists_is_a_head_request() -> None:
    transport, seen = requests_to(httpx2.Response(200), httpx2.Response(400), httpx2.Response(404))
    s = store(transport)
    assert await s.exists("a.png") is True
    assert await s.exists("b.png") is False
    assert await s.exists("c.png") is False
    assert {r.method for r in seen} == {"HEAD"}


async def test_exists_on_an_outage_raises_rather_than_answering_no() -> None:
    transport, _ = requests_to(httpx2.Response(503))
    with pytest.raises(StorageError):
        await store(transport).exists("a.png")


async def test_signed_url_is_the_full_url_storage_signs() -> None:
    signed = "/object/sign/panelwise-dev/a.png?token=abc"
    transport, seen = requests_to(httpx2.Response(200, json={"signedURL": signed}))
    assert await store(transport).signed_url("a.png", 300) == f"{URL}/storage/v1{signed}"
    (req,) = seen
    assert str(req.url) == f"{URL}/storage/v1/object/sign/panelwise-dev/a.png"
    assert json.loads(req.read()) == {"expiresIn": 300}


async def test_a_path_is_quoted_segment_by_segment() -> None:
    transport, seen = requests_to(httpx2.Response(200, content=b""))
    await store(transport).get("scripts/a b/c#d.pdf")
    assert str(seen[0].url) == f"{OBJ}/scripts/a%20b/c%23d.pdf"
