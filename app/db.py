"""Async engine/session. Postgres in prod; SQLite+aiosqlite in tests/dev-fallback."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models.base import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(url: str | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(url or settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory(url: str | None = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(url), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_test_db(url: str = "sqlite+aiosqlite:///:memory:") -> AsyncEngine:
    """Create all pos_* tables on an isolated engine (tests only)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine
