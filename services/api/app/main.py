"""The Panelwise API. Run: uv run uvicorn app.main:app"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.v1 import health
from app.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # The engine connects lazily, on first use -- building it never touches the network.
        # Deployed, DATABASE_URL is Supabase's session pooler (docs/design/deploy.md §6).
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)

        async def postgres() -> None:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        app.state.health_checks = {"postgres": postgres}
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Panelwise API", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
