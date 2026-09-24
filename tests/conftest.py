"""Shared pytest fixtures: envelope assertions, request_id, synthetic tenant markers."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def assert_envelope(body: dict, version: str = "v1") -> None:
    assert "meta" in body and body["meta"]["version"] == version
    assert "request_id" in body["meta"] and body["meta"]["request_id"]
