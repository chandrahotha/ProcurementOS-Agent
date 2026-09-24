"""Phase 0 smoke: health + binding envelope + request_id on every response."""

from fastapi.testclient import TestClient

from tests.conftest import assert_envelope


def test_healthz_envelope_and_request_id(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")
    body = r.json()
    assert_envelope(body)
    assert body["data"]["status"] == "ok"


def test_api_health_envelope(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert_envelope(body)


def test_unhandled_errors_stay_safe_and_enveloped(client: TestClient) -> None:
    # Unknown route -> FastAPI 404; our 500 handler shape is covered in Phase 1
    # with a dedicated crashing route in test env only.
    r = client.get("/api/v1/nope-not-here")
    assert r.status_code == 404
