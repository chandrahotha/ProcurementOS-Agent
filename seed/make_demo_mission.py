#!/usr/bin/env python3
"""Build a complete, realistic demo mission so every screen has real data.

`seed/seed_pos.py` creates the *master data* — users, workspaces, suppliers,
items, transactions, documents — but no mission. A fresh install therefore
opens on an empty Mission Control and every intelligence screen renders its
empty state, which makes a working product look like a stub.

This builds three missions in three different states, through the real HTTP
endpoints, so the numbers on screen are produced by the real engine and the
real gates:

* **CNC Bracket Q4** — walked all the way to the approval gate with a
  pending managerial approval. Documents, evidence spans, a plan, certified
  sourcing/cost/risk results, a candidate scenario, a negotiation draft
  inside the ladder, a brief with citations, and a live approval card.
* **Hydraulic Seal Replenishment** — walked to the analysis gate with
  results but no candidate scenario yet. Shows the "awaiting decision"
  state.
* **M6 Fastener Sourcing** — stopped in intake with a quarantined
  document. Shows the exception path and the blocked state.

It drives the API in-process (no server needed) through `TestClient`, so
the demo data is created by exactly the path a user takes.

    python seed/make_demo_mission.py --db-url sqlite+aiosqlite:///./pos_dev.db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

BUYER = "amara.buyer1@syn.example"
MANAGER = "daniel.manager@syn.example"
FINANCE = "fatima.finance@syn.example"


#: Session tokens minted by POST /api/v1/auth/login, one per persona.
_SESSIONS: dict[str, str] = {}


def _headers(client: Any, email: str, key: str | None = None) -> dict[str, str]:
    """The bearer header for a persona, logging in the first time it is needed.

    The demo data is created by exactly the path a user takes: an email and
    a password, exchanged for a session token. There is no other credential.
    """
    token = _SESSIONS.get(email)
    if token is None:
        # Imported here, not at module scope: the repository root only joins
        # sys.path in main(), so a top-level import would fail when this
        # file is run as a script.
        from seed.seed_pos import SYN_DEMO_PASSWORD

        r = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": SYN_DEMO_PASSWORD},
        )
        if r.status_code >= 400:
            raise SystemExit(f"login {email} -> {r.status_code}: {r.text[:300]}")
        token = str(r.json()["data"]["token"])
        _SESSIONS[email] = token
    h = {"Authorization": f"Bearer {token}"}
    if key:
        h["Idempotency-Key"] = key
    return h


#: The eight fields the coverage gate requires, and the values a real quote
#: carries. These are synthetic; the supplier codes are SYN-*.
SPAN_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("supplier", "SYN-SUP-01", "SYN PRECISION MACHINING (COIMBATORE) - QUOTATION Q4-2026"),
    ("unit_price", "1240.00", "CNC bracket A, 100 pcs, INR 1,240.00/pc"),
    ("currency", "INR", "priced in INR"),
    ("uom", "pcs", "per piece"),
    ("quantity", "100", "100 pcs requested"),
    ("incoterm", "EXW Coimbatore", "ex works Coimbatore"),
    ("validity", "2026-12-31", "validity 2026-12-31"),
    ("tax_mode", "exclusive", "tax exclusive 18% (GST)"),
)

#: Four quotes: three domestic in INR and one imported line invoiced in USD,
#: so the FX conversion and the cross-currency ranking are both exercised.
#: Amounts are in minor units (paise) of the invoice currency.
QUOTE_LINES: list[dict[str, Any]] = [
    {
        "line_id": "L1",
        "supplier_id": "SYN-SUP-01",
        "qty": "100",
        "uom": "pcs",
        "unit_price_minor": 124000,
        "currency": "INR",
        "tax_mode": "exclusive",
        "tax_rate": "0.18",
        "evidence_refs": ["demo-span-1"],
    },
    {
        "line_id": "L1",
        "supplier_id": "SYN-SUP-02",
        "qty": "100",
        "uom": "pcs",
        "unit_price_minor": 129500,
        "currency": "INR",
        "tax_mode": "exclusive",
        "tax_rate": "0.18",
        "evidence_refs": ["demo-span-1"],
    },
    {
        "line_id": "L1",
        "supplier_id": "SYN-SUP-03",
        "qty": "100",
        "uom": "pcs",
        "unit_price_minor": 119500,
        "currency": "INR",
        "tax_mode": "inclusive",
        "evidence_refs": ["demo-span-1"],
    },
    {
        "line_id": "L1",
        "supplier_id": "SYN-SUP-06",
        "qty": "80",
        "uom": "pcs",
        "unit_price_minor": 1180,
        "currency": "USD",
        "tax_mode": "exclusive",
        "tax_rate": "0.18",
        # 1 USD = 83.50 INR (RBI reference rate, quoted 2026-09-01).
        "fx": {
            "pair": "USD/INR",
            "rate": "83.5",
            "source": "RBI",
            "quoted_at": "2026-09-01T00:00:00Z",
        },
        "evidence_refs": ["demo-span-1"],
    },
]

TCO_ITEMS: list[dict[str, Any]] = [
    {
        "supplier_id": "SYN-SUP-01",
        "price_minor": 124000,
        "freight_minor": 4500,
        "insurance_minor": 900,
        "tooling_minor": 2500,
        "tax_minor": 22320,
        "discount_minor": 3000,
    },
    {
        "supplier_id": "SYN-SUP-02",
        "price_minor": 129500,
        "freight_minor": 6200,
        "insurance_minor": 1100,
        "tooling_minor": 2500,
        "tax_minor": 23310,
        "discount_minor": 0,
    },
    {
        "supplier_id": "SYN-SUP-03",
        "price_minor": 119500,
        "freight_minor": 5800,
        "insurance_minor": 1200,
        "tooling_minor": 4200,
        "tax_minor": 0,
        "discount_minor": 0,
    },
]

RISK_DIMENSIONS = {
    "quality": 10,
    "delivery": 8,
    "financial": 9,
    "compliance": 10,
    "geo": 7,
}

TRANSACTIONS = [
    {"on_time": True, "accepted": True, "qty": 120, "defects": 0},
    {"on_time": True, "accepted": True, "qty": 80, "defects": 1},
    {"on_time": False, "accepted": True, "qty": 60, "defects": 2},
    {"on_time": True, "accepted": True, "qty": 140, "defects": 0},
    {"on_time": True, "accepted": False, "qty": 50, "defects": 3},
    {"on_time": True, "accepted": True, "qty": 100, "defects": 1},
    {"on_time": False, "accepted": True, "qty": 90, "defects": 1},
    {"on_time": True, "accepted": True, "qty": 110, "defects": 0},
]


def _post(client: Any, path: str, email: str, body: Any = None, key: str | None = None) -> Any:
    r = client.post(
        path, headers=_headers(client, email, key), json=body if body is not None else {}
    )
    if r.status_code >= 400:
        raise SystemExit(f"POST {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()["data"]


def _get(client: Any, path: str, email: str) -> Any:
    r = client.get(path, headers=_headers(client, email))
    if r.status_code >= 400:
        raise SystemExit(f"GET {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()["data"]


def _upload(client: Any, mission_id: str, filename: str) -> str:
    path = FIXTURES / filename
    content = path.read_bytes()
    r = client.post(
        f"/api/v1/missions/{mission_id}/documents",
        headers=_headers(client, BUYER),
        files={"file": (filename, content, "application/pdf")},
    )
    if r.status_code >= 400:
        raise SystemExit(f"upload {filename} -> {r.status_code}: {r.text[:300]}")
    return str(r.json()["data"]["id"])


def _create_mission(client: Any, ws: str, title: str, budget: int, deadline: str) -> str:
    data = _post(
        client,
        "/api/v1/missions",
        BUYER,
        {
            "workspace_id": ws,
            "title": title,
            "category": "machined-components",
            "currency": "INR",
            "budget_cap_minor": budget,
            "deadline": deadline,
            "autonomy_level": "SUPERVISED",
        },
    )
    return str(data["id"])


def _spans(doc_id: str) -> list[dict[str, Any]]:
    return [
        {
            "document_id": doc_id,
            "field_name": name,
            "field_value": value,
            "quoted_text": text,
            "confidence": 0.92,
        }
        for name, value, text in SPAN_FIELDS
    ]


def _analyze_payload() -> dict[str, Any]:
    return {
        "modules": ["sourcing", "supplier", "cost", "risk"],
        "target_currency": "INR",
        "base_uom": "pcs",
        "quote_lines": QUOTE_LINES,
        "transactions": TRANSACTIONS,
        "tco_items": TCO_ITEMS,
        "risk": {"suppliers": {"SYN-SUP-01": dict(RISK_DIMENSIONS)}},
    }


def build_full_mission(client: Any, ws: str) -> str:
    """A mission walked to the approval gate with a pending approval."""
    # Budget cap 20,00,000 minor = INR 2,00,000, against a candidate cost of
    # INR 1,51,220. The award sits below the INR 5,00,000 dual-control
    # threshold, so the managerial lane alone decides it.
    mid = _create_mission(client, ws, "CNC Bracket Q4 - 1000 pcs", 20_000_000, "2026-12-31")
    doc_id = _upload(client, mid, "quote-syn-sup-01.pdf")

    _post(client, f"/api/v1/missions/{mid}/plans", BUYER)
    _post(client, f"/api/v1/missions/{mid}/plans/1/acknowledge", MANAGER)

    _post(client, f"/api/v1/missions/{mid}/evidence/spans", BUYER, _spans(doc_id))

    _post(client, f"/api/v1/missions/{mid}/advance", MANAGER, {"to_state": "plan"})
    _post(client, f"/api/v1/missions/{mid}/advance", MANAGER, {"to_state": "evidence"})
    _post(client, f"/api/v1/missions/{mid}/advance", MANAGER, {"to_state": "analysis"})

    _post(
        client, f"/api/v1/missions/{mid}/analyze", BUYER, _analyze_payload(), key="demo-analyze-1"
    )

    _post(client, f"/api/v1/missions/{mid}/advance", MANAGER, {"to_state": "scenarios"})
    _post(
        client,
        f"/api/v1/missions/{mid}/scenarios/optimize",
        MANAGER,
        {
            "scenario_id": "split-2-suppliers",
            "demand": 1000,
            "candidate": True,
            "offers": [
                {"supplier_id": "SYN-SUP-01", "unit_cost_minor": 124000, "capacity": 600},
                {"supplier_id": "SYN-SUP-03", "unit_cost_minor": 119500, "capacity": 600},
            ],
        },
    )
    _post(client, f"/api/v1/missions/{mid}/advance", MANAGER, {"to_state": "negotiation"})
    _post(
        client,
        f"/api/v1/missions/{mid}/negotiation/drafts",
        BUYER,
        {
            "supplier_id": "SYN-SUP-01",
            "candidate_cost_minor": 151220,
            "batna_cost_minor": 168000,
            "draft_price_minor": 149000,
            "text": (
                "We can hold INR 1,240.00 per piece for 1000 pieces "
                "if the order lands this quarter."
            ),
        },
    )
    _get(client, f"/api/v1/missions/{mid}/brief", BUYER)  # generates the brief
    _post(client, f"/api/v1/missions/{mid}/advance", MANAGER, {"to_state": "approval"})

    approvals = _post(
        client,
        f"/api/v1/missions/{mid}/approvals",
        BUYER,
        {"action_class": "AWARD", "payload": {"supplier_id": "SYN-SUP-01"}},
    )
    print(f"  approval pending on lane(s): {', '.join(a['lane'] for a in approvals['approvals'])}")
    return mid


def build_analysis_mission(client: Any, ws: str) -> str:
    """A mission stopped at the analysis gate: results, no decision yet."""
    mid = _create_mission(client, ws, "Hydraulic Seal Replenishment - Q1", 6_000_000, "2027-01-31")
    doc_id = _upload(client, mid, "quote-syn-sup-02.pdf")
    _post(client, f"/api/v1/missions/{mid}/plans", BUYER)
    _post(client, f"/api/v1/missions/{mid}/plans/1/acknowledge", MANAGER)
    _post(client, f"/api/v1/missions/{mid}/evidence/spans", BUYER, _spans(doc_id))
    _post(client, f"/api/v1/missions/{mid}/advance", MANAGER, {"to_state": "plan"})
    _post(client, f"/api/v1/missions/{mid}/advance", MANAGER, {"to_state": "evidence"})
    _post(client, f"/api/v1/missions/{mid}/advance", MANAGER, {"to_state": "analysis"})
    _post(
        client, f"/api/v1/missions/{mid}/analyze", BUYER, _analyze_payload(), key="demo-analyze-2"
    )
    return mid


def build_blocked_mission(client: Any, ws: str) -> str:
    """A mission stopped in intake by a quarantined document."""
    mid = _create_mission(client, ws, "M6 Fastener Sourcing - EU", 2_500_000, "2026-11-30")
    _upload(client, mid, "HOSTILE-001.pdf")
    _post(client, f"/api/v1/missions/{mid}/plans", BUYER)
    return mid


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./pos_dev.db"),
        help="async database URL (defaults to $DATABASE_URL)",
    )
    ap.add_argument("--tenant", default="SYN-TENANT-01", help="seeded tenant code")
    args = ap.parse_args(argv)

    # The app reads its settings at import time, so the URL has to be in
    # the environment before app.main is imported.
    os.environ["DATABASE_URL"] = args.db_url
    os.environ.setdefault("WEB_ORIGIN", "http://localhost:3000")
    sys.path.insert(0, str(ROOT))

    from fastapi.testclient import TestClient

    from app.main import app

    print(f"building demo missions in {args.db_url}")
    with TestClient(app, raise_server_exceptions=True) as client:
        ws = _get(client, "/api/v1/workspaces", BUYER)["workspaces"][0]["id"]
        print(f"  workspace: {ws}")

        print("building mission 1/3: CNC Bracket Q4 (at the approval gate)")
        full = build_full_mission(client, ws)
        print("building mission 2/3: Hydraulic Seal Replenishment (at the analysis gate)")
        analysis = build_analysis_mission(client, ws)
        print("building mission 3/3: M6 Fastener Sourcing (blocked in intake)")
        blocked = build_blocked_mission(client, ws)

    print("\ndemo missions ready:")
    for mid, note in (
        (full, "full walk, approval pending"),
        (analysis, "analysis done, no decision yet"),
        (blocked, "blocked in intake by a quarantined document"),
    ):
        print(f"  http://localhost:3000/agent/{mid}  ({note})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
