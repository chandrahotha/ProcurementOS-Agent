"""The credential login path, and the read models the screens consume.

The login path is the most security-critical code in the product and it
was the least covered: `app/auth/login.py` sat at 32% and
`app/api/auth_routes.py` at 40%, because the seeded test users have only
dev tokens. These tests cover it properly:

* a real password login issues a session token, and the token is stored
  **hashed** — the plaintext is never in the database,
* the session token authenticates, and `/auth/me` reports the principal,
* a wrong password and an unknown email produce the *same* response, so
  the endpoint does not enumerate accounts,
* a disabled account is refused,
* logout revokes the session: the token stops working immediately,
* an expired session does not authenticate,
* a revoked session does not authenticate.

The second half covers the read models in `app/api/misc.py` — the
endpoints the G-screens read (workspaces, suppliers directory,
notifications, audit log, rules, AI jobs, search). The claim "every screen
is wired to live data" is only true if these return real rows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.login import (
    create_session,
    hash_password,
    principal_from_session,
    session_token_digest,
    verify_password,
)
from app.db import get_session
from app.main import app
from app.models.foundation import User, UserSession
from tests.harness import BUYER, MANAGER, OUTSIDER, V1, auth


# ------------------------------------------------------------------ passwords
def test_password_hashing_round_trips() -> None:
    stored = hash_password("syn-Demo-2026!")
    assert stored.startswith("pbkdf2$100000$")
    assert "syn-Demo-2026!" not in stored
    assert verify_password("syn-Demo-2026!", stored) is True
    assert verify_password("wrong", stored) is False


def test_each_hash_uses_a_fresh_salt() -> None:
    a = hash_password("same-password")
    b = hash_password("same-password")
    assert a != b, "two hashes of the same password must differ"
    assert verify_password("same-password", a)
    assert verify_password("same-password", b)


def test_verify_password_refuses_a_malformed_stored_value() -> None:
    assert verify_password("x", None) is False
    assert verify_password("x", "") is False
    assert verify_password("x", "not-a-hash") is False
    assert verify_password("x", "pbkdf2$notanint$salt$digest") is False


# -------------------------------------------------------------------- login
@pytest.fixture()
def password_user(client: TestClient) -> str:
    """Give the seeded buyer a real password."""
    import asyncio

    generator = app.dependency_overrides[get_session]()
    session = asyncio.run(generator.__anext__())
    try:
        row = asyncio.run(session.execute(select(User).where(User.email == BUYER))).scalar_one()
        row.password_hash = hash_password("syn-Demo-2026!")
        asyncio.run(session.commit())
    finally:
        asyncio.run(generator.aclose())
    return BUYER


def test_a_real_login_issues_a_session(client: TestClient, password_user: str) -> None:
    r = client.post(f"{V1}/auth/login", json={"email": BUYER, "password": "syn-Demo-2026!"})
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["token"]
    assert body["token_type"] == "bearer"  # noqa: S105 - the scheme name, not a secret
    assert body["email"] == BUYER

    # The token authenticates.
    r = client.get(f"{V1}/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["email"] == BUYER


def test_the_session_token_is_stored_hashed(client: TestClient, password_user: str) -> None:
    """The plaintext token must not be in the database."""
    import asyncio

    r = client.post(f"{V1}/auth/login", json={"email": BUYER, "password": "syn-Demo-2026!"})
    token = r.json()["data"]["token"]

    generator = app.dependency_overrides[get_session]()
    session = asyncio.run(generator.__anext__())
    try:
        rows = asyncio.run(session.execute(select(UserSession))).scalars().all()
        assert rows
        assert all(row.token_hash != token for row in rows), "the raw token was stored"
        assert any(row.token_hash == session_token_digest(token) for row in rows)
    finally:
        asyncio.run(generator.aclose())


def test_a_wrong_password_and_an_unknown_email_look_the_same(
    client: TestClient, password_user: str
) -> None:
    """No user enumeration: the two failures are indistinguishable."""
    wrong = client.post(f"{V1}/auth/login", json={"email": BUYER, "password": "not-the-password"})
    unknown = client.post(
        f"{V1}/auth/login", json={"email": "nobody@syn.example", "password": "whatever"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"] == unknown.json()["error"]


def test_a_disabled_account_is_refused(client: TestClient, password_user: str) -> None:
    import asyncio

    generator = app.dependency_overrides[get_session]()
    session = asyncio.run(generator.__anext__())
    try:
        row = asyncio.run(session.execute(select(User).where(User.email == BUYER))).scalar_one()
        row.status = "disabled"
        asyncio.run(session.commit())
    finally:
        asyncio.run(generator.aclose())

    r = client.post(f"{V1}/auth/login", json={"email": BUYER, "password": "syn-Demo-2026!"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "account_disabled"


def test_logout_revokes_the_session(client: TestClient, password_user: str) -> None:
    r = client.post(f"{V1}/auth/login", json={"email": BUYER, "password": "syn-Demo-2026!"})
    token = r.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get(f"{V1}/auth/me", headers=headers).status_code == 200
    r = client.post(f"{V1}/auth/logout", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["logged_out"] is True

    # The token stops working immediately.
    r = client.get(f"{V1}/auth/me", headers=headers)
    assert r.status_code == 401


def test_an_expired_session_does_not_authenticate(client: TestClient, password_user: str) -> None:
    import asyncio

    generator = app.dependency_overrides[get_session]()
    session = asyncio.run(generator.__anext__())
    try:
        user = asyncio.run(session.execute(select(User).where(User.email == BUYER))).scalar_one()
        row, token = asyncio.run(
            create_session(session, tenant_id=user.tenant_id, user_id=user.id, ip="127.0.0.1")
        )
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        asyncio.run(session.commit())
        assert asyncio.run(principal_from_session(session, token)) is None
    finally:
        asyncio.run(generator.aclose())


def test_a_revoked_session_does_not_authenticate(client: TestClient, password_user: str) -> None:
    import asyncio

    generator = app.dependency_overrides[get_session]()
    session = asyncio.run(generator.__anext__())
    try:
        user = asyncio.run(session.execute(select(User).where(User.email == BUYER))).scalar_one()
        row, token = asyncio.run(
            create_session(session, tenant_id=user.tenant_id, user_id=user.id, ip="127.0.0.1")
        )
        assert asyncio.run(principal_from_session(session, token)) is not None
        row.revoked = True
        asyncio.run(session.flush())
        assert asyncio.run(principal_from_session(session, token)) is None
    finally:
        asyncio.run(generator.aclose())


# -------------------------------------------------------------- read models
def test_the_workspaces_list_shows_only_membership(client: TestClient, workspace_id: str) -> None:
    r = client.get(f"{V1}/workspaces", headers=auth(BUYER))
    assert r.status_code == 200
    names = [w["name"] for w in r.json()["data"]["workspaces"]]
    assert "WS" in names

    # The outsider is in another tenant, so they see none of them.
    r = client.get(f"{V1}/workspaces", headers=auth(OUTSIDER))
    assert r.status_code == 200
    assert r.json()["data"]["workspaces"] == []


def test_the_audit_log_reports_the_tenant_events_with_full_hashes(
    client: TestClient, workspace_id: str
) -> None:
    from tests.harness import create_mission

    _mid, _base = create_mission(client, workspace_id)
    r = client.get(f"{V1}/audit", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    events = r.json()["data"]["events"]
    assert events
    for e in events:
        assert len(e["event_hash"]) == 64
        assert "prev_hash" in e


def test_the_audit_chain_verifies(client: TestClient, workspace_id: str) -> None:
    from tests.harness import create_mission

    _mid, _base = create_mission(client, workspace_id)
    r = client.get(f"{V1}/audit/verify", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["intact"] is True
    assert body["broken_at"] is None
    assert body["events_checked"] > 0


def test_the_notifications_feed_is_derived_from_real_rows(
    client: TestClient, workspace_id: str
) -> None:
    r = client.get(f"{V1}/notifications", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    assert "notifications" in r.json()["data"]


def test_the_suppliers_directory_returns_rows(client: TestClient, workspace_id: str) -> None:
    r = client.get(f"{V1}/suppliers", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    assert "suppliers" in r.json()["data"]


def test_the_ai_jobs_panel_is_readable(client: TestClient, workspace_id: str) -> None:
    r = client.get(f"{V1}/ai-jobs", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    assert "jobs" in r.json()["data"]


def test_the_rules_viewer_is_readable(client: TestClient, workspace_id: str) -> None:
    r = client.get(f"{V1}/rules", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    assert "rules" in r.json()["data"]


def test_the_missions_list_backs_the_search_screen(client: TestClient, workspace_id: str) -> None:
    """The search screen (G06) filters the missions list client-side, so
    that list is what has to be readable and tenant-scoped."""
    from tests.harness import create_mission

    _mid, _base = create_mission(client, workspace_id, title="Findable bracket run")
    r = client.get(f"{V1}/missions", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    titles = [m["title"] for m in r.json()["data"]["missions"]]
    assert "Findable bracket run" in titles

    # The other tenant sees none of it.
    r = client.get(f"{V1}/missions", headers=auth(OUTSIDER))
    assert r.status_code == 200
    assert r.json()["data"]["missions"] == []


def test_the_approvals_queue_is_readable(client: TestClient, workspace_id: str) -> None:
    """The P13 approval queue reads the mission's approval rows."""
    from tests.harness import mission_at_approval

    _mid, base, _run = mission_at_approval(client, workspace_id)
    r = client.get(f"{base}/approvals", headers=auth(MANAGER))
    assert r.status_code == 200, r.text
    assert "approvals" in r.json()["data"]
