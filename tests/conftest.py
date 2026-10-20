"""Shared pytest fixtures: envelope assertions, request_id, synthetic tenant markers."""

from collections.abc import Iterator

import pytest

# The HTTP harness lives in tests/harness.py so it can be imported by name
# as well as used as a fixture. Re-exported here because pytest only
# auto-discovers fixtures from conftest.py.
from tests.harness import client, workspace_id  # noqa: F401


@pytest.fixture(autouse=True)
def _reset_process_state() -> Iterator[None]:
    """Clear the process-wide counters around every test.

    Two pieces of application state are deliberately global — the AI
    circuit breaker and the rate-limit counters — because both have to hold
    across requests. A test suite that makes more than `LIMIT` writes in a
    minute, or that trips the breaker with a provider-outage case, would
    otherwise start answering itself with 429s and degraded fallbacks.
    """
    from app.ai.provider import reset_circuit_breaker
    from app.core.ratelimit import reset_rate_limits

    reset_circuit_breaker()
    reset_rate_limits()
    yield
    reset_circuit_breaker()
    reset_rate_limits()


@pytest.fixture(scope="module")
def monkeypatch_module() -> Iterator[pytest.MonkeyPatch]:
    """A module-scoped monkeypatch.

    The built-in `monkeypatch` fixture is function-scoped, so a
    module-scoped fixture that needs to set an environment variable (the
    migration fixture points alembic at a throwaway database) needs its own.
    """
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def assert_envelope(body: dict, version: str = "v1") -> None:
    assert "meta" in body and body["meta"]["version"] == version
    assert "request_id" in body["meta"] and body["meta"]["request_id"]
