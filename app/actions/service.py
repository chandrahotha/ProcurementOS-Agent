"""Action Center: dry-run preview -> approval check -> idempotent execute (F14, F21).

Dry-run renders ALLOW / DENY / NEEDS-APPROVAL with exact payload + policy cite.
Execute re-verifies payload hash == approved hash, enforces idempotency
(key = mission+action+version), and dispatches ONLY via registry.dispatch.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals import service as approvals
from app.audit.writer import append_event, payload_hash
from app.models.mission import TimelineEvent
from app.tools import registry


class ActionBlockedError(Exception):
    pass


def dry_run(action_class: str, payload: dict[str, Any], quorum: bool) -> dict[str, Any]:
    # Verdict derives solely from server-computed quorum: the client-declared
    # payload_hash_match flag was removed (it was injected unconditionally by
    # the HTTP layer, making it meaningless).
    from app.approvals.policy import MATERIAL_CLASSES

    if action_class in MATERIAL_CLASSES:
        if quorum:
            return {
                "verdict": "ALLOW",
                "payload": payload,
                "policy": f"{action_class} quorum satisfied",
            }
        return {
            "verdict": "NEEDS-APPROVAL",
            "payload": payload,
            "policy": f"{action_class} requires quorum approval",
        }
    return {"verdict": "ALLOW", "payload": payload, "policy": "non-material"}


def idem_key(mission_id: str, action_class: str, version: str) -> str:
    raw = f"{mission_id}|{action_class}|{version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def _receipt(
    session: AsyncSession, tenant_id: str, mission_id: str, key: str
) -> TimelineEvent | None:
    # Receipt lookup is mission-scoped: the same key against a different
    # mission must never return the first mission's receipt.
    q = await session.execute(
        select(TimelineEvent).where(
            TimelineEvent.tenant_id == tenant_id,
            TimelineEvent.mission_id == mission_id,
            TimelineEvent.kind == "action_receipt",
        )
    )
    for ev in q.scalars().all():
        if (ev.payload or {}).get("idempotency_key") == key:
            return ev
    return None


async def _persist_external(
    session: AsyncSession,
    *,
    tenant_id: str,
    mission_id: str,
    workspace_id: str,
    tool_name: str,
    payload: dict[str, Any],
    actor_id: str,
    approval_id: str | None,
) -> dict[str, Any]:
    """Real objects of record for the gated tools — the 'action' claim becomes
    real: a PO is issued, budget is reserved, an outbox message is queued.
    The award VALUE is server-computed from certified results (never client)."""
    from app.approvals.service import certified_award_value
    from app.models.base import utcnow
    from app.models.external import BudgetReservation, MessageOutbox, PurchaseOrder
    from app.models.mission import SourcingResult

    ph = payload_hash(payload)
    if tool_name == "issue_po_intent":
        supplier_id = str(payload.get("supplier_id", ""))
        value = await certified_award_value(
            session, tenant_id=tenant_id, mission_id=mission_id, supplier_id=supplier_id
        )
        sourcing = (
            (
                await session.execute(
                    select(SourcingResult)
                    .where(
                        SourcingResult.tenant_id == tenant_id,
                        SourcingResult.mission_id == mission_id,
                        SourcingResult.supplier_id == supplier_id,
                    )
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        po = PurchaseOrder(
            tenant_id=tenant_id,
            mission_id=mission_id,
            supplier_id=supplier_id,
            po_number=f"PO-{mission_id[:8].upper()}-{ph[:6].upper()}",
            status="issued_intent",
            total_minor=value,
            lines=[
                {"line_id": r.line_id, "total_minor": r.normalized_total_minor} for r in sourcing
            ],
            payload_hash=ph,
            approval_id=approval_id,
            created_by=actor_id,
        )
        session.add(po)
        await session.flush()
        return {
            "object": "purchase_order",
            "po_id": po.id,
            "po_number": po.po_number,
            "total_minor": value,
        }
    if tool_name == "reserve_budget_intent":
        raw = payload.get("value_minor", 0)
        try:
            amount = int(raw or 0)
        except (TypeError, ValueError):
            amount = 0
        br = BudgetReservation(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            mission_id=mission_id,
            amount_minor=amount,
            status="reserved",
            payload_hash=ph,
            approval_id=approval_id,
            created_by=actor_id,
        )
        session.add(br)
        await session.flush()
        return {"object": "budget_reservation", "reservation_id": br.id, "amount_minor": amount}
    if tool_name == "send_supplier_message":
        mo = MessageOutbox(
            tenant_id=tenant_id,
            mission_id=mission_id,
            supplier_id=str(payload.get("supplier_id", "")),
            channel="email",
            recipient=str(payload.get("recipient", "")),
            subject=str(payload.get("subject", "Procurement update")),
            body=str(payload.get("text", payload.get("message", ""))),
            status="queued",
            payload_hash=ph,
            approval_id=approval_id,
            created_by=actor_id,
        )
        # Transport-gated delivery: when OUTBOX_WEBHOOK_URL is configured the
        # message really sends; otherwise it stays queued for the drain (the
        # approval is what authorized it either way).
        sent = await _deliver(mo)
        if sent:
            mo.status = "sent"
            mo.sent_at = utcnow()
        session.add(mo)
        await session.flush()
        return {"object": "message_outbox", "message_id": mo.id, "status": mo.status}
    return {}


async def _deliver(mo: Any) -> bool:
    """Best-effort real send through the configured transport. False when no
    transport is configured (the message stays queued in the outbox)."""
    try:
        import httpx

        from app.core.config import settings

        if not settings.outbox_webhook_url:
            return False
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                settings.outbox_webhook_url,
                json={
                    "to": mo.recipient,
                    "subject": mo.subject,
                    "body": mo.body,
                    "mission_id": mo.mission_id,
                },
            )
            return r.status_code < 300
    except Exception:
        return False


async def execute(
    session: AsyncSession,
    *,
    tenant_id: str,
    mission_id: str,
    workspace_id: str = "",
    action_class: str,
    payload: dict[str, Any],
    tool_name: str,
    actor_id: str,
    request_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    # Idempotent replay: same key returns the original receipt.
    existing = await _receipt(session, tenant_id, mission_id, idempotency_key)
    if existing is not None:
        return {"receipt": existing.payload, "replayed": True}
    try:
        ok = await approvals.quorum_met(
            session,
            tenant_id=tenant_id,
            mission_id=mission_id,
            action_class=action_class,
            payload=payload,
        )
    except approvals.ApprovalError as e:
        # Server-side value check refused (e.g. AWARD without certified TCO).
        await append_event(
            session,
            tenant_id=tenant_id,
            action="award_blocked_no_approval",
            actor_id=actor_id,
            mission_id=mission_id,
            request_id=request_id,
            object_type="action",
            reason=f"{action_class} execute denied: {e}",
        )
        raise ActionBlockedError(f"{action_class} blocked: {e}") from e
    if not ok:
        await append_event(
            session,
            tenant_id=tenant_id,
            action="award_blocked_no_approval",
            actor_id=actor_id,
            mission_id=mission_id,
            request_id=request_id,
            object_type="action",
            reason=f"{action_class} execute denied: no quorum approval",
        )
        raise ActionBlockedError(f"{action_class} blocked: no quorum approval")
    # Payload-hash match is enforced by quorum_met (hash over exact payload).
    approval_id = payload_hash(payload)[:16]
    try:
        out = registry.dispatch(
            tool_name,
            dict(payload),
            actor_id=actor_id,
            approval_id=approval_id,
            idempotency_key=idempotency_key,
        )
    except (registry.UnknownToolError, registry.ToolDeniedError) as e:
        await append_event(
            session,
            tenant_id=tenant_id,
            action="action_blocked",
            actor_id=actor_id,
            mission_id=mission_id,
            request_id=request_id,
            object_type="action",
            reason=str(e),
        )
        raise ActionBlockedError(str(e)) from e
    receipt = {
        "mission_id": mission_id,
        "action_class": action_class,
        "tool": tool_name,
        "payload_hash": payload_hash(payload),
        "idempotency_key": idempotency_key,
        "result": out["result"],
    }
    # Real objects of record (A2): the gated tools' outputs persist — a PO,
    # a budget reservation, or an outbox message now exists.
    external = await _persist_external(
        session,
        tenant_id=tenant_id,
        mission_id=mission_id,
        workspace_id=workspace_id,
        tool_name=tool_name,
        payload=payload,
        actor_id=actor_id,
        approval_id=approval_id,
    )
    if external:
        receipt["external"] = external
    session.add(
        TimelineEvent(
            tenant_id=tenant_id,
            mission_id=mission_id,
            kind="action_receipt",
            payload=receipt,
            actor_id=actor_id,
        )
    )
    await append_event(
        session,
        tenant_id=tenant_id,
        action="action_executed",
        actor_id=actor_id,
        mission_id=mission_id,
        request_id=request_id,
        object_type="action",
        after={"payload_hash": receipt["payload_hash"]},
    )
    await session.flush()
    return {"receipt": receipt, "replayed": False}
