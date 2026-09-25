"""Shared pytest fixtures: envelope assertions, request_id, synthetic tenant markers."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """Client with an isolated in-memory sqlite session override: the
    healthz DB probe must be environment-independent (the CI unit job has no
    postgres service; local runs may not have one either)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    mk = async_sessionmaker(engine, expire_on_commit=False)

    async def override():
        async with mk() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def assert_envelope(body: dict, version: str = "v1") -> None:
    assert "meta" in body and body["meta"]["version"] == version
    assert "request_id" in body["meta"] and body["meta"]["request_id"]
