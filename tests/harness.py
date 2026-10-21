"""Shared HTTP test harness.

`tests/test_api.py` grew one function that walked the entire W1->W8
lifecycle, and the finding T9 called that out: a single giant test with
tolerance assertions (`status in (403, 404)`) cannot tell an intended
denial from an accidental one, and a failure in the middle of it reports
one line of context for a hundred lines of setup.

This module holds the setup that every HTTP test needs — an in-memory
sqlite database, a seeded tenant with one user per persona, a workspace, an
out-of-tenant user — so a test file can be about one behaviour instead of
about the harness. `tests/test_api.py` uses it too, and the lifecycle walk
is split into the phases it actually asserts.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.login import create_session, hash_password
from app.db import get_session
from app.main import app
from app.models.base import Base
from app.models.foundation import User, Workspace

TENANT = "t-api"
V1 = "/api/v1"

BUYER = "buyer@x.io"
MANAGER = "daniel@x.io"
FINANCE = "fatima@x.io"
COMPLIANCE = "chen@x.io"
OUTSIDER = "other@x.io"

#: The password every seeded persona shares. A test user signs in the way a
#: person does — with an email and a password — because that is the only
#: credential the API accepts.
TEST_PASSWORD = "syn-Demo-2026!"

#: The seeded personas' password hash, computed once. Hashing it per test
#: would cost five PBKDF2 stretches on every single test; the salt being
#: shared between synthetic test users is irrelevant, and the salt-per-user
#: property is pinned by `test_each_hash_uses_a_fresh_salt`.
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)

#: Session tokens minted by `create_session`, one per persona, populated by
#: the `client` fixture. There is no developer token to fall back on.
_SESSIONS: dict[str, str] = {}


def auth(email: str, key: str | None = None) -> dict[str, str]:
    """The bearer header for a persona.

    The token is a real session token — the same one `POST /auth/login`
    would mint — issued when the `client` fixture seeded the tenant.
    """
    token = _SESSIONS.get(email)
    if token is None:
        raise AssertionError(f"no session for {email!r}: the client fixture did not run")
    hs = {"Authorization": f"Bearer {token}"}
    if key:
        hs["Idempotency-Key"] = key
    return hs


async def _seed(engine: Any) -> tuple[dict[str, str], str]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    mk = async_sessionmaker(engine, expire_on_commit=False)
    async with mk() as s:
        users: dict[str, str] = {}
        roles_by_email: dict[str, list[str]] = {}
        crew = [
            ("Buyer", BUYER, ["Buyer"]),
            ("Manager", MANAGER, ["ProcurementManager", "Buyer"]),
            ("Finance", FINANCE, ["FinanceReviewer"]),
            ("Compliance", COMPLIANCE, ["ComplianceReviewer"]),
        ]
        for name, email, roles in crew:
            u = User(
                tenant_id=TENANT,
                email=email,
                name=name,
                password_hash=TEST_PASSWORD_HASH,
            )
            s.add(u)
            await s.flush()
            users[email] = u.id
            roles_by_email[email] = roles
        ws = Workspace(
            tenant_id=TENANT,
            name="WS",
            budget_currency="INR",
            members=[
                {"user_id": uid, "roles": roles_by_email[email]} for email, uid in users.items()
            ],
        )
        s.add(ws)
        await s.flush()
        other = User(
            tenant_id="t-other",
            email=OUTSIDER,
            name="O",
            password_hash=TEST_PASSWORD_HASH,
        )
        s.add(other)
        await s.commit()
        # A real session per persona, issued by the same function the login
        # endpoint uses. The endpoint's own password-verification path is
        # covered by `tests/test_auth_and_read_models.py`.
        for email in (BUYER, MANAGER, FINANCE, COMPLIANCE, OUTSIDER):
            _row, token = await create_session(
                s,
                tenant_id="t-other" if email == OUTSIDER else TENANT,
                user_id=other.id if email == OUTSIDER else users[email],
            )
            _SESSIONS[email] = token
        await s.commit()
        return users, ws.id


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """A TestClient bound to a fresh in-memory database and a seeded tenant.

    `raise_server_exceptions=True` (the default) is deliberate: the old
    harness turned it off, which swallowed every server-side exception and
    let a raw 500 masquerade as a handled error response. B53 asked for
    exactly this to be turned back on.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    users, ws = asyncio.run(_seed(engine))
    mk = async_sessionmaker(engine, expire_on_commit=False)

    async def override() -> Any:
        async with mk() as s:
            yield s

    app.dependency_overrides[get_session] = override
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        _SESSIONS.clear()
        app.dependency_overrides.pop(get_session, None)
        asyncio.run(engine.dispose())


@pytest.fixture()
def workspace_id(client: TestClient) -> str:
    """The seeded workspace id, fetched over HTTP as a member would."""
    r = client.get(f"{V1}/workspaces", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    return r.json()["data"]["workspaces"][0]["id"]


# --------------------------------------------------------------------------
# Phase builders
#
# The lifecycle used to be one 250-line function. These builders take a
# mission up to a given phase so each test can start where it needs to and
# assert one thing. A failure now names the behaviour that broke instead
# of pointing at a line in a long walk.
# --------------------------------------------------------------------------

#: The eight fields the coverage gate requires.
REQUIRED_FIELDS = (
    "supplier",
    "unit_price",
    "currency",
    "uom",
    "quantity",
    "incoterm",
    "validity",
    "tax_mode",
)

#: Two quote lines in different currencies and UoMs, with FX.
ANALYZE_PAYLOAD: dict[str, Any] = {
    "modules": ["sourcing", "supplier", "cost", "risk"],
    "target_currency": "INR",
    "base_uom": "pcs",
    "quote_lines": [
        {
            "line_id": "L1",
            "supplier_id": "S-A",
            "qty": "48",
            "uom": "pcs",
            "unit_price_minor": 90,
            "currency": "INR",
            "tax_mode": "inclusive",
            "evidence_refs": ["sp1"],
        },
        {
            "line_id": "L1",
            "supplier_id": "S-B",
            "qty": "2",
            "uom": "box",
            "unit_price_minor": 1000,
            "currency": "USD",
            "tax_mode": "exclusive",
            "tax_rate": "0.19",
            "fx": {
                "pair": "USD/INR",
                "rate": "83.5",
                "source": "RBI",
                "quoted_at": "2026-09-01T00:00:00Z",
            },
            "evidence_refs": ["sp2"],
        },
    ],
    "transactions": [{"on_time": True, "accepted": True, "qty": 100, "defects": 1}] * 4,
    "tco_items": [
        {
            "supplier_id": "S-A",
            "price_minor": 4320,
            "freight_minor": 200,
            "tax_minor": 300,
            "discount_minor": 100,
        }
    ],
    "risk": {
        "suppliers": {
            "S-A": {"quality": 10, "delivery": 10, "financial": 10, "compliance": 10, "geo": 10}
        }
    },
}

#: The AWARD payload. The forged low/high values cannot change the lanes:
#: the server computes the award value from certified results.
AWARD_PAYLOAD: dict[str, Any] = {"supplier_id": "S-A", "value_minor": 1, "threshold_minor": 1}


def create_mission(c: TestClient, ws: str, title: str = "CNC Brackets Q4") -> tuple[str, str]:
    """A mission in `intake`. Returns (mission_id, base_path)."""
    r = c.post(
        f"{V1}/missions",
        headers=auth(BUYER),
        json={
            "workspace_id": ws,
            "title": title,
            "currency": "INR",
            "budget_cap_minor": 10000000,
            "deadline": "2026-12-31",
            "autonomy_level": "SUPERVISED",
        },
    )
    assert r.status_code == 200, r.text
    mid = r.json()["data"]["id"]
    return mid, f"{V1}/missions/{mid}"


def upload_clean_document(c: TestClient, base: str) -> str:
    """A clean quote document. Returns its id."""
    r = c.post(
        f"{base}/documents",
        headers=auth(BUYER),
        files={"file": ("q.pdf", b"%PDF-1.4 quote", "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "clean", r.text
    return str(r.json()["data"]["id"])


def generate_and_acknowledge_plan(c: TestClient, base: str) -> int:
    """A plan, acknowledged by a manager. Returns the plan version."""
    r = c.post(f"{base}/plans", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    version = int(r.json()["data"]["version"])
    r = c.post(f"{base}/plans/{version}/acknowledge", headers=auth(MANAGER))
    assert r.status_code == 200, r.text
    return version


def record_spans(c: TestClient, base: str, doc_id: str) -> list[dict[str, Any]]:
    """One span per required field."""
    spans = [
        {
            "document_id": doc_id,
            "field_name": f,
            "field_value": "v",
            "quoted_text": f"quote text {f}",
            "confidence": 0.9,
        }
        for f in REQUIRED_FIELDS
    ]
    r = c.post(f"{base}/evidence/spans", headers=auth(BUYER), json=spans)
    assert r.status_code == 200, r.text
    return list(r.json()["data"]["spans"])


def advance(c: TestClient, base: str, to_state: str) -> Any:
    """Advance the mission. Fails the test if the gate refuses."""
    r = c.post(f"{base}/advance", headers=auth(MANAGER), json={"to_state": to_state})
    assert r.status_code == 200, (to_state, r.text)
    return r


def analyze(c: TestClient, base: str, key: str = "k-an") -> str:
    """Run the analysis suite. Returns the run id."""
    r = c.post(f"{base}/analyze", headers=auth(BUYER, key), json=ANALYZE_PAYLOAD)
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["run_id"])


def mission_at_plan(c: TestClient, ws: str) -> tuple[str, str, str]:
    """A mission with a document, a plan, and an acknowledged plan.

    Returns (mission_id, base_path, document_id). The mission is in
    `evidence` state: the intake checklist passed and the plan was
    acknowledged.
    """
    mid, base = create_mission(c, ws)
    doc_id = upload_clean_document(c, base)
    generate_and_acknowledge_plan(c, base)
    advance(c, base, "plan")
    advance(c, base, "evidence")
    return mid, base, doc_id


def mission_at_analysis(c: TestClient, ws: str) -> tuple[str, str, str]:
    """A mission through the analysis gate. Returns (id, base, run_id)."""
    mid, base, doc_id = mission_at_plan(c, ws)
    record_spans(c, base, doc_id)
    advance(c, base, "analysis")
    run_id = analyze(c, base)
    return mid, base, run_id


def create_candidate_scenario(c: TestClient, base: str) -> str:
    """A candidate scenario. The negotiation gate needs one."""
    r = c.post(
        f"{base}/scenarios/optimize",
        headers=auth(MANAGER),
        json={
            "scenario_id": "split-1",
            "demand": 100,
            "candidate": True,
            "offers": [
                {"supplier_id": "S-A", "unit_cost_minor": 50, "capacity": 60},
                {"supplier_id": "S-B", "unit_cost_minor": 60, "capacity": 60},
            ],
        },
    )
    assert r.status_code == 200, r.text
    return "split-1"


def create_draft(c: TestClient, base: str) -> dict[str, Any]:
    """A negotiation draft inside the ladder. The approval gate needs one."""
    r = c.post(
        f"{base}/negotiation/drafts",
        headers=auth(BUYER),
        json={
            "supplier_id": "S-A",
            "candidate_cost_minor": 9000,
            "batna_cost_minor": 10000,
            "draft_price_minor": 9500,
            "text": "Hi, can you do 9500?",
        },
    )
    assert r.status_code == 200, r.text
    return dict(r.json()["data"])


def mission_at_negotiation(c: TestClient, ws: str) -> tuple[str, str, str]:
    """A mission at the negotiation gate. Returns (id, base, run_id)."""
    mid, base, run_id = mission_at_analysis(c, ws)
    advance(c, base, "scenarios")
    create_candidate_scenario(c, base)
    advance(c, base, "negotiation")
    return mid, base, run_id


def mission_at_approval(c: TestClient, ws: str) -> tuple[str, str, str]:
    """A mission at the approval gate. Returns (id, base, run_id).

    The approval gate wants two things: a Decision Brief (generated by
    reading the brief endpoint) and a negotiation draft whose ladder is in
    policy. Both are produced here, in the order the gate reads them.
    """
    mid, base, run_id = mission_at_negotiation(c, ws)
    create_draft(c, base)
    r = c.get(f"{base}/brief", headers=auth(BUYER))
    assert r.status_code == 200, r.text
    advance(c, base, "approval")
    return mid, base, run_id
