"""The database: one declarative base, and the engine and sessions built from Settings.

docs/design/deploy.md §6 (T009). Migrations are Alembic's (migrations/); the app never creates
tables itself.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings) -> AsyncEngine:
    # Lazy: building it never touches the network. Deployed, DATABASE_URL is Supabase's session
    # pooler, which keeps prepared statements working (deploy.md §6).
    return create_async_engine(settings.database_url, pool_pre_ping=True)


def make_sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
