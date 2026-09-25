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

_engines: dict[str, AsyncEngine] = {}
_factories: dict[str, async_sessionmaker[AsyncSession]] = {}


def get_engine(url: str | None = None) -> AsyncEngine:
    # Cache keyed by URL (B54): a second call with a different URL must not
    # silently return the first engine.
    key = url or settings.database_url
    engine = _engines.get(key)
    if engine is None:
        engine = create_async_engine(key, pool_pre_ping=True)
        _engines[key] = engine
    return engine


def get_session_factory(url: str | None = None) -> async_sessionmaker[AsyncSession]:
    key = url or settings.database_url
    factory = _factories.get(key)
    if factory is None:
        factory = async_sessionmaker(get_engine(url), class_=AsyncSession, expire_on_commit=False)
        _factories[key] = factory
    return factory


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
