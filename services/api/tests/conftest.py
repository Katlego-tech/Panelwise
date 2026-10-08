"""The `db` fixture: a real Postgres for tests marked `db` (docs/design/deploy.md §6, T009).

`TEST_DATABASE_URL` names it. `scripts/gate.sh` starts a throwaway Postgres 17.11 and sets it, with
`PANELWISE_REQUIRE_DB=1`: under the gate a missing database fails the run; by hand it skips.
"""

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings

API = Path(__file__).resolve().parents[1]
TABLES = ("frame_audits", "frames", "jobs", "projects")  # truncated before each test


def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        message = "no TEST_DATABASE_URL: run bash scripts/gate.sh, or point it at a Postgres 17"
        if os.environ.get("PANELWISE_REQUIRE_DB") == "1":
            pytest.fail(message)
        pytest.skip(message)
    url = Settings(database_url=url).database_url
    # The fixture truncates every table: never let it near a real database (deploy.md §6).
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        pytest.fail(f"TEST_DATABASE_URL must name a database ending in _test, not {name!r}")
    return url


@pytest.fixture(scope="session")
def migrated() -> str:
    """The test database upgraded to head once per session: this also tests the migration."""
    url = database_url()
    config = Config(str(API / "alembic.ini"))
    config.set_main_option("script_location", str(API / "migrations"))
    config.attributes["database_url"] = url
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return url


@pytest.fixture
async def sessions(migrated: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(migrated)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
