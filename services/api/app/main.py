"""The Panelwise API. Run: uv run uvicorn app.main:app"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.v1 import health
from app.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # Both clients connect lazily, on first use -- building them never touches the network.
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        redis = Redis.from_url(settings.redis_url)  # pyright: ignore[reportUnknownMemberType]

        async def postgres() -> None:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        async def redis_ping() -> None:
            await redis.ping()  # pyright: ignore[reportUnknownMemberType]

        app.state.health_checks = {"postgres": postgres, "redis": redis_ping}
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="Panelwise API", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
