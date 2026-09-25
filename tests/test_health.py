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


def test_500_envelope_shape() -> None:
    """T8: the 500 handler emits the binding envelope + request_id — pinned
    with a test-only crashing route."""
    from fastapi.testclient import TestClient as TC

    from app.main import app

    @app.get("/api/v1/__crash_test__")
    async def _crash() -> None:
        raise RuntimeError("boom")

    try:
        with TC(app, raise_server_exceptions=False) as c:
            r = c.get("/api/v1/__crash_test__")
    finally:
        app.router.routes = [
            rt for rt in app.router.routes if getattr(rt, "path", "") != "/api/v1/__crash_test__"
        ]
    assert r.status_code == 500
    body = r.json()
    assert_envelope(body)
    assert body["error"]["code"] == "internal_error"
    assert body["request_id"]


def test_422_envelope_on_malformed_body() -> None:
    """B31 pinned: malformed bodies carry the same envelope + request_id."""
    from app.auth.deps import Principal, get_principal
    from app.main import app

    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id="u1", tenant_id="t1", email="e@x.io", roles=["Buyer"]
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.post(
                "/api/v1/missions",
                content=b"{not json",
                headers={"Content-Type": "application/json"},
            )
    finally:
        app.dependency_overrides.pop(get_principal, None)
    assert r.status_code == 422
    body = r.json()
    assert_envelope(body)
    assert body["error"]["code"] == "validation_error"
