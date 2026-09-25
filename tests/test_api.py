"""Issue 1: full HTTP lifecycle W1-W8 + authZ matrix (sqlite, override)."""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import app
from app.models.base import Base
from app.models.foundation import User, Workspace

TENANT = "t-api"
V1 = "/api/v1"


async def _seed(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    mk = async_sessionmaker(engine, expire_on_commit=False)
    async with mk() as s:
        users = {}
        crew = [
            ("Buyer", "buyer@x.io"),
            ("Manager", "daniel@x.io"),
            ("Finance", "fatima@x.io"),
            ("Compliance", "chen@x.io"),
        ]
        for name, email in crew:
            u = User(tenant_id=TENANT, email=email, name=name, api_token=f"tok-{email}")
            s.add(u)
            await s.flush()
            users[email] = u.id
        ws = Workspace(
            tenant_id=TENANT,
            name="WS",
            budget_currency="EUR",
            members=[{"user_id": uid} for uid in users.values()],
        )
        s.add(ws)
        await s.flush()
        other = User(tenant_id="t-other", email="o@x.io", name="O", api_token="tok-other")
        s.add(other)
        await s.commit()
        return users, ws.id


def _setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    users, ws = asyncio.run(_seed(engine))
    mk = async_sessionmaker(engine, expire_on_commit=False)

    async def override():
        async with mk() as s:
            yield s

    app.dependency_overrides[get_session] = override
    return TestClient(app, raise_server_exceptions=False), users, ws


def H(email, key=None):
    hs = {"Authorization": f"Bearer tok-{email}"}
    if key:
        hs["Idempotency-Key"] = key
    return hs


HO = {"Authorization": "Bearer tok-other"}
B = "buyer@x.io"
MGR = "daniel@x.io"
FIN = "fatima@x.io"


def test_full_lifecycle_and_matrix():
    c, users, ws = _setup()

    # --- auth matrix ---
    r = c.get(f"{V1}/missions")
    assert r.status_code == 401 and r.json()["request_id"]
    r = c.get(f"{V1}/missions", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401

    # --- W1 create ---
    r = c.post(
        f"{V1}/missions",
        headers=H(B),
        json={
            "workspace_id": ws,
            "title": "CNC Brackets Q4",
            "currency": "EUR",
            "budget_cap_minor": 10000000,
            "deadline": "2026-12-31",
            "autonomy_level": "SUPERVISED",
        },
    )
    assert r.status_code == 200, r.text
    mid = r.json()["data"]["id"]
    base = f"{V1}/missions/{mid}"
    assert r.headers.get("X-Request-ID")
    assert r.json()["meta"]["version"] == "v1"
    r = c.get(base, headers=HO)
    assert r.status_code in (403, 404)  # outsider sees nothing useful

    # dial increase as buyer -> 403; manager -> ok
    dial = {"autonomy_level": "GUARDED"}
    r = c.patch(base, headers=H(B), json=dial)
    assert r.status_code == 403
    r = c.patch(base, headers=H(MGR), json=dial)
    assert r.status_code == 200

    # --- W2 documents ---
    r = c.post(
        f"{base}/documents",
        headers=H(B),
        files={"file": ("q.pdf", b"%PDF-1.4 quote", "application/pdf")},
    )
    assert r.json()["data"]["status"] == "clean", r.text
    doc_id = r.json()["data"]["id"]
    r = c.post(
        f"{base}/documents",
        headers=H(B),
        files={
            "file": (
                "e.docx",
                b"PK\x03\x04 vbaProject evil",
                "application/vnd.openxmlformats-officedocument" ".wordprocessingml.document",
            )
        },
    )
    assert r.json()["data"]["status"] == "rejected"

    # --- plans ---
    r = c.post(f"{base}/plans", headers=H(B))
    assert r.json()["data"]["version"] == 1
    assert r.json()["data"]["tasks"] == 10
    r = c.post(f"{base}/plans/1/acknowledge", headers=H(B))
    assert r.status_code == 403
    r = c.post(f"{base}/plans/1/acknowledge", headers=H(MGR))
    assert r.status_code == 200
    r = c.get(f"{base}/plans/1/diff", headers=H(B))
    assert r.status_code == 200

    # --- tasks ---
    r = c.get(f"{base}/tasks", headers=H(B))
    assert len(r.json()["data"]["tasks"]) == 10
    retry = f"{base}/tasks/extract-quotes/retry"
    r = c.post(retry, headers=H(B))
    assert r.status_code == 422  # key required
    r = c.post(retry, headers=H(B, "k-t1"))
    assert r.json()["data"]["status"] == "queued"
    r = c.post(f"{base}/tasks/extract-quotes/review", headers=H(B), json={"decision": "accept"})
    assert r.json()["data"]["status"] == "done"

    # --- evidence: all 8 required fields backed ---
    fields = [
        "supplier",
        "unit_price",
        "currency",
        "uom",
        "quantity",
        "incoterm",
        "validity",
        "tax_mode",
    ]
    spans = [
        {
            "document_id": doc_id,
            "field_name": f,
            "field_value": "v",
            "quoted_text": f"quote text {f}",
            "confidence": 0.9,
        }
        for f in fields
    ]
    r = c.post(f"{base}/evidence/spans", headers=H(B), json=spans)
    assert len(r.json()["data"]["spans"]) == 8
    sid = r.json()["data"]["spans"][0]["id"]
    r = c.patch(
        f"{base}/evidence/{sid}",
        headers=H(B),
        json={"field_value": "12.40", "reason": "decimal fix"},
    )
    assert r.json()["data"]["reanalysis_recommended"] is True

    # --- advance: bad jump refused, chain advances ---
    r = c.post(f"{base}/advance", headers=H(B), json={"to_state": "approval"})
    assert r.status_code in (403, 422)
    for to_state in ("plan", "evidence", "analysis"):
        r = c.post(f"{base}/advance", headers=H(MGR), json={"to_state": to_state})
        assert r.status_code == 200, (to_state, r.text)

    # --- W3 analyze + idempotent replay ---
    fx_usd = {
        "pair": "USD/EUR",
        "rate": "0.92",
        "source": "ECB",
        "quoted_at": "2026-09-01T00:00:00Z",
    }
    payload = {
        "modules": ["sourcing", "supplier", "cost", "risk"],
        "target_currency": "EUR",
        "base_uom": "pcs",
        "quote_lines": [
            {
                "line_id": "L1",
                "supplier_id": "S-A",
                "qty": "48",
                "uom": "pcs",
                "unit_price_minor": 90,
                "currency": "EUR",
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
                "fx": fx_usd,
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
    r = c.post(f"{base}/analyze", headers=H(B, "k-an"), json=payload)
    assert r.status_code == 200, r.text
    run_id = r.json()["data"]["run_id"]
    r = c.post(f"{base}/analyze", headers=H(B, "k-an"), json=payload)
    assert r.json()["data"]["replayed"] is True
    for path in ("sourcing", "cost", "risk"):
        r = c.get(f"{base}/results/{path}", headers=H(B))
        assert r.status_code == 200 and r.json()["data"]

    # --- W4 scenarios ---
    offers = [
        {"supplier_id": "S-A", "unit_cost_minor": 50, "capacity": 60},
        {"supplier_id": "S-B", "unit_cost_minor": 60, "capacity": 60},
    ]
    scen = {"scenario_id": "split-1", "demand": 100, "candidate": True, "offers": offers}
    r = c.post(f"{base}/scenarios/optimize", headers=H(B), json=scen)
    assert r.status_code == 403
    r = c.post(f"{base}/scenarios/optimize", headers=H(MGR), json=scen)
    assert r.status_code == 200, r.text
    bad = dict(scen, scenario_id="bad-1", demand=1000)
    r = c.post(f"{base}/scenarios", headers=H(B), json=bad)
    assert r.status_code == 422
    assert r.json()["error"]["details"]["notes"]

    # --- W5 drafts ---
    draft = {
        "supplier_id": "S-A",
        "candidate_cost_minor": 9000,
        "batna_cost_minor": 10000,
        "text": "Hi, can you do 9500?",
    }
    r = c.post(
        f"{base}/negotiation/drafts", headers=H(B), json={**draft, "draft_price_minor": 12000}
    )
    assert r.status_code == 422
    r = c.post(
        f"{base}/negotiation/drafts", headers=H(B), json={**draft, "draft_price_minor": 9500}
    )
    assert r.json()["data"]["sent"] is False

    # --- W6 brief + approvals ---
    r = c.get(f"{base}/brief", headers=H(B))
    assert r.json()["data"]["winner_supplier_id"] == "S-A"
    # Server-computed value (04 s2): S-A's certified TCO is 4,720 minor
    # (EUR 47.20) < the 50k threshold, so AWARD needs the managerial lane
    # only. The forged low/high values in the payload cannot change lanes.
    award = {"supplier_id": "S-A", "value_minor": 1, "threshold_minor": 1}
    r = c.post(
        f"{base}/approvals",
        headers=H(B),
        json={"action_class": "AWARD", "payload": award},
    )
    aids = {a["lane"]: a["id"] for a in r.json()["data"]["approvals"]}
    assert set(aids) == {"managerial"}
    # AWARD for a supplier with no certified TCO is refused outright.
    r = c.post(
        f"{base}/approvals",
        headers=H(B),
        json={"action_class": "AWARD", "payload": {"supplier_id": "S-Z"}},
    )
    assert r.status_code == 422
    # Execute before any decision -> blocked (AGENT-002 at HTTP level).
    ex_body = {"action_class": "AWARD", "payload": award, "tool_name": "issue_po_intent"}
    r = c.post(f"{base}/actions/execute", headers=H(B, "k-ex"), json=ex_body)
    assert r.status_code == 403
    # Dry-run before approval says NEEDS-APPROVAL, not ALLOW.
    r = c.post(
        f"{base}/actions/dry-run", headers=H(B), json={"action_class": "AWARD", "payload": award}
    )
    assert r.json()["data"]["verdict"] == "NEEDS-APPROVAL"
    # Finance cannot decide a managerial-lane row (lane roles enforced).
    mgr_decide = f"{base}/approvals/{aids['managerial']}/decide"
    r = c.post(mgr_decide, headers=H(FIN), json={"decision": "approved", "reason": "x"})
    assert r.status_code == 403
    r = c.post(mgr_decide, headers=H(MGR), json={"decision": "approved", "reason": "ok"})
    assert r.json()["data"]["quorum_met"] is True
    r = c.post(f"{base}/actions/execute", headers=H(B, "k-ex"), json=ex_body)
    assert r.status_code == 200
    assert r.json()["data"]["replayed"] is False
    # Execute is idempotent: replay returns the original receipt.
    r = c.post(f"{base}/actions/execute", headers=H(B, "k-ex"), json=ex_body)
    assert r.json()["data"]["replayed"] is True

    # --- runs/replay, export, timeline, alias ---
    r = c.get(f"{base}/runs", headers=H(B))
    assert r.json()["data"]["runs"]
    r = c.post(f"{base}/runs/{run_id}/replay", headers=H(MGR))
    assert r.json()["data"]["verdict"] == "match"
    assert r.json()["data"]["tco_integrity"] is True
    r = c.post(f"{base}/export", headers=H(B), json={"format": "CSV"})
    assert r.status_code == 200 and len(r.content) > 0
    r = c.post(
        f"{base}/export", headers=H(B), json={"format": "CSV", "mission_ids": [mid, "m-smuggled"]}
    )
    assert r.status_code == 403
    for fmt in ("XLSX", "PDF"):
        r = c.post(f"{base}/export", headers=H(B), json={"format": fmt})
        assert r.status_code == 200 and len(r.content) > 100, fmt
    r = c.get(f"{base}/timeline", headers=H(B))
    assert len(r.json()["data"]["events"]) > 10
    r = c.get(f"{V1}/cases/missions", headers=H(B))
    assert r.status_code == 200 and r.json()["data"]["missions"]
