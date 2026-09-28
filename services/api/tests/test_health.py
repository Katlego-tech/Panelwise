"""GET /api/v1/health -- the contract in TASKS.md T002."""

import asyncio
import time

from fastapi.testclient import TestClient

from app.api.v1.health import Check, get_checks
from app.core.config import Settings
from app.main import create_app


async def ok() -> None:
    return None


def client_with(checks: dict[str, Check], timeout_s: float = 1.0) -> TestClient:
    app = create_app(Settings(health_check_timeout_s=timeout_s))
    app.dependency_overrides[get_checks] = lambda: checks
    return TestClient(app)


def test_all_checks_pass_returns_200_ok() -> None:
    res = client_with({"postgres": ok, "redis": ok}).get("/api/v1/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


def test_a_failing_check_returns_503_degraded_and_names_the_exception_type() -> None:
    async def redis_down() -> None:
        raise ConnectionRefusedError("Connection refused")

    res = client_with({"postgres": ok, "redis": redis_down}).get("/api/v1/health")

    assert res.status_code == 503
    assert res.json() == {
        "status": "degraded",
        "checks": {"postgres": "ok", "redis": "error: ConnectionRefusedError"},
    }


def test_error_messages_are_never_returned() -> None:
    async def leaky() -> None:
        raise RuntimeError("postgresql://panelwise:hunter2@db:5432/panelwise")

    res = client_with({"postgres": leaky, "redis": ok}).get("/api/v1/health")

    assert "hunter2" not in res.text
    assert res.json()["checks"]["postgres"] == "error: RuntimeError"


def test_a_hanging_check_times_out_instead_of_hanging_the_endpoint() -> None:
    async def hangs() -> None:
        await asyncio.sleep(10)

    started = time.monotonic()
    res = client_with({"postgres": hangs, "redis": ok}, timeout_s=0.05).get("/api/v1/health")

    assert time.monotonic() - started < 2
    assert res.status_code == 503
    assert res.json()["checks"]["postgres"] == "error: TimeoutError"


def test_checks_run_concurrently() -> None:
    async def slow() -> None:
        await asyncio.sleep(0.3)

    started = time.monotonic()
    res = client_with({"postgres": slow, "redis": slow}).get("/api/v1/health")

    assert res.status_code == 200
    assert time.monotonic() - started < 0.55
