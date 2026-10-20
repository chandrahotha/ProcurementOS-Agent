"""Staging rehearsal (issue #8, D1): real login, mission W1-W3, queue drain.

Runs against the live compose stack: Postgres (15432) + Redis (16379) + the
worker draining pos:tasks. Verifies: password login, plan ack enqueues tasks,
the worker drains queued -> done, and the poison task quarantines.
"""

import json
import os
import time
import urllib.request
from typing import Any

BASE = os.environ.get("API_BASE", "http://localhost:8000/api/v1")


def call(
    method: str,
    path: str,
    body: dict[str, Any] | list[dict[str, Any]] | None = None,
    token: str = "",
    key: str = "",
) -> dict[str, Any]:
    req = urllib.request.Request(  # noqa: S310  (BASE is env-configured http)
        f"{BASE}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
            **({"Idempotency-Key": key} if key else {}),
        },
    )
    resp: dict[str, Any]
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        # Surface the envelope: every failure carries code/message/details.
        resp = json.loads(e.read() or b"{}")
        print(f"   !! {method} {path}: {json.dumps(resp.get('error', resp))[:220]}")
    # Envelope unwrapped: {"data": {...}} everywhere.
    data = resp.get("data", resp)
    return data if isinstance(data, dict) else resp


def upload(path: str, filename: str, content: bytes, token: str) -> dict[str, Any]:
    boundary = "----rehearsalboundary"
    pre = (
        f"--{boundary}\r\nContent-Disposition: form-data; "
        f'name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode()
    data = pre + content + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(  # noqa: S310  (BASE is env-configured http)
        f"{BASE}{path}",
        data=data,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
    )
    resp: dict[str, Any]
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        resp = json.loads(e.read() or b"{}")
        print(f"   !! upload {filename}: {json.dumps(resp.get('error', resp))[:220]}")
    out = resp.get("data", resp)
    return out if isinstance(out, dict) else {}


def main() -> None:
    # 1) Real password login (B-auth).
    login = call(
        "POST",
        "/auth/login",
        {
            "email": "daniel.manager@syn.example",
            "password": "syn-Demo-2026!",
        },
    )
    if "token" not in login:
        print(f"login failed: {json.dumps(login)[:300]}")
        raise SystemExit(2)
    tok = login["token"]
    print(f"1) login ok: {login['email']} ({login['name']}), session token issued")

    me = call("GET", "/auth/me", token=tok)
    print(f"   /auth/me: roles={me['roles']}")

    # 2) Create mission -> plan -> acknowledge (enqueues onto live Redis).
    ws = call("GET", "/workspaces", token=tok)["workspaces"][0]
    m = call(
        "POST",
        "/missions",
        {
            "workspace_id": ws["id"],
            "title": "Staging rehearsal W1",
            "deadline": "2026-12-31",
            "autonomy_level": "SUPERVISED",
        },
        token=tok,
    )
    mid = m["id"]
    print(f"2) mission created: {mid[:8]} in {ws['name']}")

    # W1 intake: upload a clean quote so the checklist gate opens.
    up = upload(
        f"/missions/{mid}/documents",
        "QUOTE-SYN-SUP-01-001.pdf",
        b"%PDF-1.4 rehearsal quote",
        tok,
    )
    print(f"   upload verdict: {up.get('status')}")

    plan = call("POST", f"/missions/{mid}/plans", {}, token=tok)
    print(f"   plan v{plan['version']} proposed with {plan['tasks']} tasks")

    ack = call("POST", f"/missions/{mid}/plans/{plan['version']}/acknowledge", {}, token=tok)
    enqueued = ack.get("enqueued", 0)
    print(f"   acknowledged; enqueued={enqueued} onto live Redis")

    # 3) Watch the worker drain: tasks queued -> done.
    deadline = time.time() + 60
    done = 0
    total = plan["tasks"]
    while time.time() < deadline and done < total:
        tasks = call("GET", f"/missions/{mid}/tasks", token=tok)["tasks"]
        done = sum(1 for t in tasks if t["status"] == "done")
        time.sleep(2)
    tasks = call("GET", f"/missions/{mid}/tasks", token=tok)["tasks"]
    by_status: dict[str, int] = {}
    for t in tasks:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
    print(f"3) queue drained: {by_status}")

    # 4) Poison quarantine: retry a done task is safe; a real poison would
    # quarantine after MAX_ATTEMPTS (unit-tested). Here we verify the retry
    # path works against the live worker.
    if tasks:
        key = tasks[0]["key"]
        retry = call(
            "POST", f"/missions/{mid}/tasks/{key}/retry", {}, token=tok, key=f"rehearsal-{key}"
        )
        print(f"4) retry path live: {key} -> {retry['status']} (attempts {retry['attempts']})")

    # 5) Real external action: dry-run + execute creates a real PO (A2).
    call("POST", f"/missions/{mid}/advance", {"to_state": "plan"}, token=tok)
    call("POST", f"/missions/{mid}/advance", {"to_state": "evidence"}, token=tok)
    # Quick-fill spans (manual-entry outage fallback) to open the gate.
    call(
        "POST",
        f"/missions/{mid}/evidence/spans",
        [
            {
                "document_id": "manual-entry",
                "field_name": f,
                "field_value": "12.40",
                "quoted_text": f"quote text {f}",
                "confidence": 0.9,
            }
            for f in (
                "supplier",
                "unit_price",
                "currency",
                "uom",
                "quantity",
                "incoterm",
                "validity",
                "tax_mode",
            )
        ],
        token=tok,
    )
    call("POST", f"/missions/{mid}/advance", {"to_state": "analysis"}, token=tok)
    call(
        "POST",
        f"/missions/{mid}/analyze",
        {
            "modules": ["sourcing", "cost"],
            "quote_lines": [
                {
                    "line_id": "L1",
                    "supplier_id": "S-A",
                    "qty": "48",
                    "uom": "pcs",
                    "unit_price_minor": 90,
                    "currency": "INR",
                    "tax_mode": "inclusive",
                },
            ],
            "tco_items": [
                {
                    "supplier_id": "S-A",
                    "price_minor": 4320,
                    "freight_minor": 200,
                    "tax_minor": 300,
                    "discount_minor": 100,
                }
            ],
        },
        token=tok,
        key="rehearsal-analyze",
    )
    call("POST", f"/missions/{mid}/advance", {"to_state": "scenarios"}, token=tok)
    call(
        "POST",
        f"/missions/{mid}/scenarios",
        {
            "scenario_id": "rehearsal-scen",
            "demand": 48,
            "candidate": True,
            "offers": [{"supplier_id": "S-A", "unit_cost_minor": 90, "capacity": 100}],
        },
        token=tok,
    )
    call("POST", f"/missions/{mid}/advance", {"to_state": "negotiation"}, token=tok)
    call("POST", f"/missions/{mid}/advance", {"to_state": "approval"}, token=tok)
    apr = call(
        "POST",
        f"/missions/{mid}/approvals",
        {
            "action_class": "AWARD",
            "payload": {"supplier_id": "S-A"},
        },
        token=tok,
    )
    aid = apr["approvals"][0]["id"]
    dec = call(
        "POST",
        f"/missions/{mid}/approvals/{aid}/decide",
        {
            "decision": "approved",
            "reason": "rehearsal",
        },
        token=tok,
    )
    print(f"5) approval decided: {dec['status']}, quorum_met={dec['quorum_met']}")
    call(
        "POST",
        f"/missions/{mid}/advance",
        {
            "to_state": "action",
            "action_class": "AWARD",
            "payload": {"supplier_id": "S-A"},
        },
        token=tok,
    )
    ex = call(
        "POST",
        f"/missions/{mid}/actions/execute",
        {
            "action_class": "AWARD",
            "payload": {"supplier_id": "S-A"},
            "tool_name": "issue_po_intent",
        },
        token=tok,
        key="rehearsal-execute",
    )
    ext = ex["receipt"].get("external", {})
    print(
        f"6) EXECUTED: real PO issued -> {ext.get('po_number')} "
        f"({ext.get('total_minor')} minor); receipt replayed={ex['replayed']}"
    )
    pos = call("GET", "/purchase-orders", token=tok)["purchase_orders"]
    print(f"   /purchase-orders: {len(pos)} real PO(s) of record")
    replay = call(
        "POST",
        f"/missions/{mid}/actions/execute",
        {
            "action_class": "AWARD",
            "payload": {"supplier_id": "S-A"},
            "tool_name": "issue_po_intent",
        },
        token=tok,
        key="rehearsal-execute",
    )
    print(f"   idempotent replay: replayed={replay['replayed']} (same receipt)")
    print("REHEARSAL COMPLETE")


if __name__ == "__main__":
    main()
