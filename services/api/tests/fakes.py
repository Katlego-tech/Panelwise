"""Test doubles shared by the API tests: a token verifier and an in-memory AssetStore."""

import uuid

from app.core.auth import AuthError, Caller


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
