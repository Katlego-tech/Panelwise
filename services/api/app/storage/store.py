"""Assets in Supabase Storage: uploaded PDFs (T053) and, from T026, frame images.

storyboard.md §6 `AssetStore` / `SupabaseStore`. The bucket is private; only the secret key
reads or writes it, and a browser gets an image only through a signed URL (storyboard.md §8).
Supabase Storage answers some errors as 400 with the real status inside the body
(`"statusCode": "409"` for an existing object, `"404"` for a missing one; checked 2026-10-02).
"""

from typing import Protocol, cast
from urllib.parse import quote

import httpx2


class StorageError(RuntimeError):
    """Storage refused or failed. The message names the operation and status, never a key."""


class AssetNotFound(StorageError):
    pass


class AssetStore(Protocol):
    async def exists(self, path: str) -> bool: ...
    async def get(self, path: str) -> bytes: ...
    async def put(self, path: str, data: bytes, content_type: str) -> None: ...  # idempotent
    async def signed_url(self, path: str, expires_in_s: int) -> str: ...


def _inner_status(response: httpx2.Response) -> str | None:
    """The status Supabase puts in the body of a 400 (or a real 4xx), if any."""
    try:
        body: object = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    status: object = cast(dict[str, object], body).get("statusCode")
    return None if status is None else str(status)


class SupabaseStore:
    def __init__(
        self, *, url: str, secret_key: str, bucket: str, client: httpx2.AsyncClient
    ) -> None:
        self._base = f"{url.rstrip('/')}/storage/v1"
        self._bucket = bucket
        self._client = client
        self._headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}"}

    def _object(self, path: str, kind: str = "object") -> str:
        return f"{self._base}/{kind}/{quote(self._bucket)}/{quote(path, safe='/')}"

    async def exists(self, path: str) -> bool:
        response = await self._client.head(self._object(path), headers=self._headers)
        if response.status_code == 200:
            return True
        if response.status_code in (400, 404):  # Storage says "missing" as a bare 400 to HEAD
            return False
        raise StorageError(f"exists: storage answered {response.status_code}")

    async def get(self, path: str) -> bytes:
        response = await self._client.get(self._object(path), headers=self._headers)
        if response.status_code == 200:
            return response.content
        if response.status_code == 404 or _inner_status(response) == "404":
            raise AssetNotFound(f"get: no object at {path}")
        raise StorageError(f"get: storage answered {response.status_code}")

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        """Upload without overwriting. An existing path is left as is and counts as success:
        paths are content-addressed or unique (storyboard.md §6)."""
        response = await self._client.post(
            self._object(path),
            content=data,
            headers=self._headers | {"Content-Type": content_type, "x-upsert": "false"},
        )
        if response.status_code == 200:
            return
        if response.status_code == 409 or _inner_status(response) == "409":
            return
        raise StorageError(f"put: storage answered {response.status_code}")

    async def signed_url(self, path: str, expires_in_s: int) -> str:
        response = await self._client.post(
            self._object(path, "object/sign"),
            json={"expiresIn": expires_in_s},
            headers=self._headers,
        )
        if response.status_code != 200:
            raise StorageError(f"signed_url: storage answered {response.status_code}")
        return f"{self._base}{response.json()['signedURL']}"
