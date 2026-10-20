"""Workspaces, scenarios/approvals lists, audit + rules read models, settle.

These are the read paths the screens consume (P02 workspace picker, P10
scenario list, P13 approval queue, G13 audit log, G16 rules viewer) plus
the settle action that closes the action->report gate.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import aud, err, log_timeline, must_mission, not_found, rows_for
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.models.foundation import Approval, AuditEvent, Supplier, SupplierSite, Workspace
from app.models.mission import (
    RiskResult,
    RuleVersion,
    ScenarioResult,
    SourcingResult,
)

router = APIRouter()

WRITERS = {BUYER, MANAGER, ADMIN}


@router.get("/workspaces")
async def list_workspaces(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Workspaces the principal is a member of (Admin sees all in tenant)."""
    q = select(Workspace).where(Workspace.tenant_id == principal.tenant_id)
    rows = (await session.execute(q)).scalars().all()
    out = []
    for ws in rows:
        member = any(m.get("user_id") == principal.user_id for m in (ws.members or []))
        if member or "Admin" in principal.roles:
            out.append(
                {
                    "id": ws.id,
                    "name": ws.name,
                    "budget_currency": ws.budget_currency,
                }
            )
    return ok({"workspaces": out}, get_request_id(request))


@router.get("/missions/{mission_id}/scenarios")
async def list_scenarios(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rows = await rows_for(session, ScenarioResult, m.id, tenant_id=m.tenant_id, limit=500)
    return ok(
        {
            "scenarios": [
                {
                    "scenario_id": r.scenario_id,
                    "allocations": r.allocations,
                    "objective_value": r.objective_value,
                    "candidate": r.candidate,
                    "savings_vs_baseline": r.savings_vs_baseline,
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.get("/missions/{mission_id}/approvals")
async def list_approvals(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """All approval rows for the mission (P13 queue + quorum read)."""
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    from app.api.common import rows_for as rf

    rows = await rf(session, Approval, m.id, tenant_id=m.tenant_id, limit=500)
    return ok(
        {
            "approvals": [
                {
                    "id": r.id,
                    "lane": r.lane,
                    "status": r.status,
                    "action_class": r.action_class,
                    "expires_at": r.expires_at,
                    "payload_hash": r.payload_hash[:16],
                    # The approved payload itself, not only its hash: an
                    # approver has to see what they are approving, and the
                    # action panel has to carry the *same* payload back or
                    # the hash-locked advance is refused.
                    "payload": r.payload_json or {},
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.get("/audit")
async def audit_log(
    request: Request,
    limit: int = 200,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Tenant-wide hash-chained events, newest first (G13)."""
    q = select(AuditEvent).where(AuditEvent.tenant_id == principal.tenant_id)
    q = q.order_by(AuditEvent.created_at.desc()).limit(max(0, min(limit, 500)))
    rows = (await session.execute(q)).scalars().all()
    return ok(
        {
            "events": [
                {
                    "id": r.id,
                    "action": r.action,
                    "object_type": r.object_type,
                    "mission_id": r.mission_id,
                    "actor_id": r.actor_id,
                    "request_id": r.request_id,
                    "reason": r.reason,
                    # Full hashes + prev_hash (B34): clients can verify the
                    # chain; truncation weakened tamper evidence.
                    "event_hash": r.event_hash,
                    "prev_hash": r.prev_hash,
                    "at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.get("/audit/verify")
async def audit_verify(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Re-walk the tenant's hash chain end to end (B34): tamper detection."""
    rid = get_request_id(request)
    # The walk lives in app/audit/writer.py so the endpoint and the
    # action->report gate (`audit_complete`) use one implementation and
    # cannot disagree about whether the chain is intact.
    from app.audit.writer import verify_chain

    result = await verify_chain(session, principal.tenant_id)
    return ok(
        {
            "events_checked": result["events"],
            "intact": result["intact"],
            "broken_at": result["broken_at"],
        },
        rid,
    )


@router.get("/rules")
async def rules(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Rule versions in this tenant (G16 read model)."""
    q = select(RuleVersion).where(RuleVersion.tenant_id == principal.tenant_id)
    q = q.order_by(RuleVersion.created_at.desc())
    rows = (await session.execute(q)).scalars().all()
    return ok(
        {
            "rules": [
                {
                    "version": r.version,
                    "effective_from": r.effective_from,
                    "weights": r.weights,
                    "tolerances": r.tolerances,
                    "fx_policy": r.fx_policy,
                    "changelog": r.changelog,
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.post("/missions/{mission_id}/actions/settle")
async def settle_actions(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Record that approved actions are executed or explicitly skipped (04 s1)."""
    rid = get_request_id(request)
    if not set(principal.roles) & WRITERS:
        return err(403, "forbidden", "Forbidden for role.", rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="actions_settled",
        payload={"by": principal.user_id},
        actor_id=principal.user_id,
    )
    await aud(session, request, principal, "actions_settled", m, "mission", m.id)
    await session.commit()
    return ok({"mission_id": m.id, "settled": True}, rid)


@router.get("/purchase-orders")
async def list_purchase_orders(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Real POs of record (A2/A3): issued ONLY by the issue_po_intent tool
    after quorum approval."""
    rid = get_request_id(request)
    from app.models.external import PurchaseOrder

    rows = (
        (
            await session.execute(
                select(PurchaseOrder)
                .where(PurchaseOrder.tenant_id == principal.tenant_id)
                .order_by(PurchaseOrder.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return ok(
        {
            "purchase_orders": [
                {
                    "id": r.id,
                    "mission_id": r.mission_id,
                    "po_number": r.po_number,
                    "supplier_id": r.supplier_id,
                    "status": r.status,
                    "total_minor": r.total_minor,
                    "lines": r.lines,
                    "at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        },
        rid,
    )


@router.get("/budget-reservations")
async def list_budget_reservations(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Real budget holds (A2/A3): reserved ONLY by reserve_budget_intent
    after approval."""
    rid = get_request_id(request)
    from app.models.external import BudgetReservation

    rows = (
        (
            await session.execute(
                select(BudgetReservation)
                .where(BudgetReservation.tenant_id == principal.tenant_id)
                .order_by(BudgetReservation.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return ok(
        {
            "reservations": [
                {
                    "id": r.id,
                    "mission_id": r.mission_id,
                    "workspace_id": r.workspace_id,
                    "status": r.status,
                    "amount_minor": r.amount_minor,
                    "currency": r.currency,
                    "at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        },
        rid,
    )


@router.get("/messages")
async def list_outbox(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Transactional outbox (A2/A3): approved messages queued for delivery;
    transport-gated send."""
    rid = get_request_id(request)
    from app.models.external import MessageOutbox

    rows = (
        (
            await session.execute(
                select(MessageOutbox)
                .where(MessageOutbox.tenant_id == principal.tenant_id)
                .order_by(MessageOutbox.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    return ok(
        {
            "messages": [
                {
                    "id": r.id,
                    "mission_id": r.mission_id,
                    "supplier_id": r.supplier_id,
                    "recipient": r.recipient,
                    "subject": r.subject,
                    "status": r.status,
                    "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                    "at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        },
        rid,
    )


@router.get("/suppliers")
async def list_suppliers(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Tenant supplier directory (G09, B48): Supplier rows joined with the
    latest certified risk/sourcing results, newest first."""
    rid = get_request_id(request)
    q = (
        select(Supplier)
        .where(Supplier.tenant_id == principal.tenant_id)
        .order_by(Supplier.code)
        .limit(500)
    )
    suppliers = (await session.execute(q)).scalars().all()
    risks = (
        (
            await session.execute(
                select(RiskResult)
                .where(RiskResult.tenant_id == principal.tenant_id)
                .order_by(RiskResult.created_at.desc())
                .limit(500)
            )
        )
        .scalars()
        .all()
    )
    sourcing = (
        (
            await session.execute(
                select(SourcingResult)
                .where(SourcingResult.tenant_id == principal.tenant_id)
                .order_by(SourcingResult.created_at.desc())
                .limit(500)
            )
        )
        .scalars()
        .all()
    )
    latest_risk: dict[str, RiskResult] = {}
    for rk in risks:
        latest_risk.setdefault(rk.supplier_id, rk)
    latest_rank: dict[str, int] = {}
    for sr in sourcing:
        latest_rank.setdefault(sr.supplier_id, sr.rank)
    out = [
        {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "country": s.country,
            "status": s.status,
            "risk_composite": latest_risk[s.id].composite if s.id in latest_risk else None,
            "risk_band": latest_risk[s.id].band if s.id in latest_risk else None,
            "last_rank": latest_rank.get(s.id),
        }
        for s in suppliers
    ]
    return ok({"suppliers": out}, rid)


@router.get("/suppliers/{supplier_id}")
async def supplier_profile(
    supplier_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Supplier profile (G10, B48): site, KPIs, risk history, sourcing ranks."""
    rid = get_request_id(request)
    from engine.supplier_intel import compute_kpis

    s = (
        await session.execute(
            select(Supplier).where(
                Supplier.id == supplier_id, Supplier.tenant_id == principal.tenant_id
            )
        )
    ).scalar_one_or_none()
    if s is None:
        return err(404, "not_found", "No such supplier.", rid)
    site = (
        await session.execute(select(SupplierSite).where(SupplierSite.supplier_id == s.id))
    ).scalar_one_or_none()
    from app.models.foundation import Transaction

    txns = (
        (
            await session.execute(
                select(Transaction)
                .where(
                    Transaction.tenant_id == principal.tenant_id, Transaction.supplier_id == s.id
                )
                .order_by(Transaction.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    risks = (
        (
            await session.execute(
                select(RiskResult)
                .where(RiskResult.tenant_id == principal.tenant_id, RiskResult.supplier_id == s.id)
                .order_by(RiskResult.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return ok(
        {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "country": s.country,
            "status": s.status,
            "site": {
                "locale": site.locale if site else None,
                "incoterm_default": site.incoterm_default if site else None,
                "lead_time_days": site.lead_time_days if site else None,
            },
            "kpis": compute_kpis(
                [
                    {
                        "on_time": t.on_time,
                        "accepted": t.accepted,
                        "qty": t.qty,
                        "defects": t.defects,
                    }
                    for t in txns
                ]
            ),
            "risk_history": [
                {
                    "composite": r.composite,
                    "band": r.band,
                    "weights_version": r.weights_version,
                    "at": r.created_at.isoformat(),
                }
                for r in risks
            ],
        },
        rid,
    )


@router.get("/ai-jobs")
async def list_ai_jobs(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Tenant-wide AI run history (G17, B48): jobs + their results."""
    rid = get_request_id(request)
    from app.models.foundation import AIJob, AIResult

    jobs = (
        (
            await session.execute(
                select(AIJob)
                .where(AIJob.tenant_id == principal.tenant_id)
                .order_by(AIJob.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    job_ids = [j.id for j in jobs]
    results: dict[str, AIResult] = {}
    if job_ids:
        rows = (
            (await session.execute(select(AIResult).where(AIResult.job_id.in_(job_ids)).limit(500)))
            .scalars()
            .all()
        )
        for r in rows:
            results.setdefault(r.job_id, r)
    return ok(
        {
            "jobs": [
                {
                    "id": j.id,
                    "mission_id": j.mission_id,
                    "purpose": j.purpose,
                    "provider": j.provider,
                    "model_version": j.model_version,
                    "status": j.status,
                    "error": j.error,
                    "result_label": results[j.id].label if j.id in results else None,
                    # The citations travel with the row: an AI claim without
                    # them is not reviewable (POS-AI-HAL-01).
                    "evidence_refs": (
                        list(results[j.id].evidence_refs or []) if j.id in results else []
                    ),
                    "at": j.created_at.isoformat(),
                }
                for j in jobs
            ]
        },
        rid,
    )


@router.get("/notifications")
async def list_notifications(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Derived notification feed (G05, B48): pending approvals, gate
    rejections, task blocks — from real rows, newest first."""
    rid = get_request_id(request)
    items: list[dict[str, Any]] = []
    pending = (
        (
            await session.execute(
                select(Approval)
                .where(Approval.tenant_id == principal.tenant_id, Approval.status == "pending")
                .order_by(Approval.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    for a in pending:
        items.append(
            {
                "kind": "approval_pending",
                "title": f"{a.lane} lane awaiting decision ({a.action_class})",
                "mission_id": a.mission_id,
                "at": a.created_at.isoformat(),
            }
        )
    denials = (
        (
            await session.execute(
                select(AuditEvent)
                .where(
                    AuditEvent.tenant_id == principal.tenant_id,
                    AuditEvent.action.in_(
                        [
                            "award_blocked_no_approval",
                            "action_blocked",
                            "document_rejected",
                            "transition_refused",
                            "unknown_tool_blocked",
                            "task_failed",
                            "waiver_denied",
                        ]
                    ),
                )
                .order_by(AuditEvent.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    for d in denials:
        items.append(
            {
                "kind": "gate_denied",
                "title": d.action + (f" — {d.reason}" if d.reason else ""),
                "mission_id": d.mission_id,
                "at": d.created_at.isoformat(),
            }
        )
    items.sort(key=lambda i: i["at"], reverse=True)
    return ok({"notifications": items[:100]}, rid)
