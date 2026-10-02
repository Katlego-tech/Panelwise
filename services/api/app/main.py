"""The Panelwise API. Run: uv run uvicorn app.main:app"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1 import health
from app.core.config import Settings
from app.db import make_engine, make_sessions
from app.jobs import fail_interrupted

log = logging.getLogger(__name__)


async def sweep(sessions: async_sessionmaker[AsyncSession]) -> None:
    """web.md §4.1: a job still QUEUED or RUNNING at startup was cut off by the restart. If the
    database is unreachable, log and start anyway: the health check reports it, and the next
    start sweeps."""
    try:
        async with sessions() as session, session.begin():
            count = await fail_interrupted(session)
    except Exception as exc:
        log.warning("restart sweep skipped: the database is unreachable (%s)", type(exc).__name__)
        return
    if count:
        log.info("restart sweep: %d interrupted job(s) marked failed", count)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # The engine connects lazily, on first use -- building it never touches the network.
        # Deployed, DATABASE_URL is Supabase's session pooler (docs/design/deploy.md §6).
        engine = make_engine(settings)
        sessions = make_sessions(engine)

        async def postgres() -> None:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        app.state.health_checks = {"postgres": postgres}
        app.state.sessions = sessions
        await sweep(sessions)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Panelwise API", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
