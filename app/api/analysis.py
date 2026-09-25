"""Native analysis suite + certified results (05 W3, F06–F09).

Analyze runs the deterministic engine over caller-supplied inputs (quote
lines, transactions, TCO items, risk dimensions) plus evidence refs, pins
rule_version, and persists result rows + a MissionRun. Idempotency-Key replays
return the original run instead of recomputing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import aud, err, log_timeline, must_mission, not_found, rows_for
from app.audit.writer import payload_hash
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.models.mission import CostResult, MissionRun, RiskResult, SourceLink, SourcingResult
from engine.money import FxRate

router = APIRouter()
WRITE_ROLES = {BUYER, MANAGER, ADMIN}


class AnalyzeBody(BaseModel):
    modules: list[str] = ["sourcing", "supplier", "cost", "risk"]
    quote_lines: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []
    tco_items: list[dict[str, Any]] = []
    risk: dict[str, Any] = {}
    target_currency: str = "EUR"
    base_uom: str = "pcs"


def _fx_of(d: dict[str, Any]) -> FxRate | None:
    f = d.get("fx")
    if not f:
        return None
    try:
        pair = f["pair"]
        rate = f["rate"]
        source = f["source"]
        quoted_at = f["quoted_at"]
    except KeyError as e:
        # KeyError is not caught by the ValueError handler: re-raise as
        # ValueError so malformed fx rows map to 422, never a raw 500 (B16).
        raise ValueError(f"fx row missing {e.args[0]}") from None
    return FxRate(
        pair=str(pair), rate=Decimal(str(rate)), source=str(source), quoted_at=str(quoted_at)
    )


@router.post("/missions/{mission_id}/analyze")
async def run_analysis(
    mission_id: str,
    body: AnalyzeBody,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    if not set(principal.roles) & WRITE_ROLES:
        return err(403, "forbidden", "Forbidden for role.", get_request_id(request))
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rid = get_request_id(request)
    for mod in body.modules:
        if mod not in ("sourcing", "supplier", "cost", "risk"):
            return err(422, "validation_error", f"Unknown module {mod}.", rid)
    key = request.headers.get("Idempotency-Key", "")
    doc = {"mission": m.id, "body": body.model_dump()}
    inputs_hash = payload_hash({"key": key, **doc} if key else doc)
    if key:
        dup_q = select(MissionRun).where(
            MissionRun.mission_id == m.id,
            MissionRun.inputs_hash == inputs_hash,
            # Failed runs never replay: a retried identical request re-runs
            # instead of returning the failed run forever (T19).
            MissionRun.status != "failed",
        )
        dup = (
            await session.execute(dup_q.order_by(MissionRun.created_at.desc()).limit(1))
        ).scalar_one_or_none()
        if dup is not None:
            return ok({"run_id": dup.id, "replayed": True, "status": dup.status}, rid)
    from app.tools.registry import TOOL_VERSIONS
    from engine import cost_intel, risk_intel
    from engine import sourcing_compare as sc
    from engine.supplier_intel import compute_kpis

    run = MissionRun(
        tenant_id=m.tenant_id,
        mission_id=m.id,
        plan_version=1,
        trigger="manual",
        inputs_hash=inputs_hash,
        rule_version=m.rule_version,
        tool_versions=TOOL_VERSIONS,
        status="ok",
    )
    session.add(run)
    await session.flush()
    summary: dict[str, Any] = {"run_id": run.id, "replayed": False}
    try:
        if "sourcing" in body.modules and body.quote_lines:
            normed = []
            refs_by_key: dict[tuple[str, str], list[Any]] = {}
            for ql in body.quote_lines:
                g = ql.get
                # Validated extraction (B16): malformed keys/values raise
                # ValueError (mapped to 422), never a raw 500.
                line_id = str(g("line_id", ""))
                supplier_id = str(g("supplier_id", ""))
                if not line_id or not supplier_id:
                    raise ValueError("each quote line needs line_id and supplier_id")
                qty_raw = g("qty", "0")
                try:
                    qty = Decimal(str(qty_raw))
                except Exception:
                    raise ValueError(f"invalid qty {qty_raw!r} on line {line_id}") from None
                refs = list(g("evidence_refs", []))
                line = sc.QuoteLine(
                    line_id=line_id,
                    supplier_id=supplier_id,
                    qty=qty,
                    uom=g("uom", body.base_uom),
                    unit_price_minor=int(g("unit_price_minor", 0)),
                    currency=g("currency", body.target_currency),
                    tax_mode=g("tax_mode", "exclusive"),
                    tax_rate=Decimal(str(g("tax_rate", "0"))),
                    compliant=bool(g("compliant", True)),
                    price_uom=str(g("price_uom", "") or ""),
                    evidence_refs=refs,
                )
                normed.append(
                    sc.normalize_line(line, body.base_uom, body.target_currency, _fx_of(ql))
                )
                refs_by_key[(line_id, supplier_id)] = refs
            ranked = sc.rank_lines(normed)
            result_rows = []
            for n in ranked:
                # Evidence refs persist (B4): every material number traces to
                # its source spans.
                row = SourcingResult(
                    tenant_id=m.tenant_id,
                    mission_id=m.id,
                    run_id=run.id,
                    line_id=n.line_id,
                    supplier_id=n.supplier_id,
                    normalized_total_minor=n.normalized_total_minor,
                    rank=n.rank,
                    compliant_bool=n.compliant,
                    evidence_refs=refs_by_key.get((n.line_id, n.supplier_id), []),
                )
                session.add(row)
                result_rows.append(row)
            await session.flush()
            for row in result_rows:
                # SourceLink joins to the real result row id (B4), never a
                # synthetic string.
                session.add(
                    SourceLink(
                        tenant_id=m.tenant_id,
                        result_id=row.id,
                        evidence_span_ids=list(row.evidence_refs or []),
                        role="supporting",
                    )
                )
            summary["sourcing"] = len(ranked)
        if "supplier" in body.modules and body.transactions:
            summary["supplier_kpis"] = compute_kpis(body.transactions)
        if "cost" in body.modules:
            for item in body.tco_items:
                g = item.get
                r = cost_intel.tco(
                    int(g("price_minor", 0)),
                    int(g("freight_minor", 0)),
                    int(g("insurance_minor", 0)),
                    int(g("tooling_minor", 0)),
                    int(g("tax_minor", 0)),
                    int(g("discount_minor", 0)),
                    currency=g("currency", body.target_currency),
                    target_ccy=body.target_currency,
                    fx=_fx_of(item),
                    fx_tolerance_days=int(g("fx_tolerance_days", 30)),
                )
                session.add(
                    CostResult(
                        tenant_id=m.tenant_id,
                        mission_id=m.id,
                        run_id=run.id,
                        supplier_id=g("supplier_id", ""),
                        scenario_id=g("scenario_id", ""),
                        tco_minor=r["tco_minor"],
                        build_up=r["build_up"],
                        fx_sources=[r["fx"]] if r["fx"] else [],
                        stale_flag=r["stale_flag"],
                    )
                )
            summary["cost_items"] = len(body.tco_items)
        if "risk" in body.modules and body.risk:
            suppliers_dims = body.risk.get("suppliers", {})
            for supplier_id, dd in suppliers_dims.items():
                dims: dict[str, int] = {}
                for k, v in dd.items():
                    iv = int(v)
                    if not 0 <= iv <= 100:
                        raise ValueError(f"risk dimension {k} must be 0-100")
                    dims[k] = iv
                s = risk_intel.score(dims)
                session.add(
                    RiskResult(
                        tenant_id=m.tenant_id,
                        mission_id=m.id,
                        run_id=run.id,
                        supplier_id=supplier_id,
                        dimensions=s["dimensions"],
                        weights_version=m.rule_version,
                        composite=s["composite"],
                        band=s["band"],
                    )
                )
            summary["risk_scored"] = len(suppliers_dims)
    except ValueError as e:
        # B3: partial result rows from a failed run must never persist —
        # roll back, then record the failure as a run row only (no results,
        # so GET .../results/* stays certified).
        await session.rollback()
        failed = MissionRun(
            tenant_id=m.tenant_id,
            mission_id=m.id,
            plan_version=1,
            trigger="manual",
            inputs_hash=inputs_hash,
            rule_version=m.rule_version,
            tool_versions=TOOL_VERSIONS,
            status="failed",
            step_log=[{"event": "analysis.failed", "error": str(e)}],
        )
        session.add(failed)
        await session.commit()
        return err(422, "analysis_failed", str(e), rid)
    run.step_log = [{"event": "analysis.completed", "modules": body.modules, "summary": summary}]
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="analysis.completed",
        payload={"run_id": run.id, "modules": body.modules},
        actor_id=principal.user_id,
    )
    await aud(
        session,
        request,
        principal,
        "analysis_run",
        m,
        "run",
        run.id,
        after={"modules": body.modules},
    )
    await session.commit()
    summary["status"] = run.status
    return ok(summary, rid)


@router.get("/missions/{mission_id}/results/sourcing")
async def sourcing_results(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rows = await rows_for(session, SourcingResult, m.id, tenant_id=m.tenant_id, limit=500)
    return ok(
        {
            "lines": [
                {
                    "line_id": r.line_id,
                    "supplier_id": r.supplier_id,
                    "normalized_total_minor": r.normalized_total_minor,
                    "rank": r.rank,
                    "compliant": r.compliant_bool,
                    "evidence_refs": r.evidence_refs,
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.get("/missions/{mission_id}/results/cost")
async def cost_results(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rows = await rows_for(session, CostResult, m.id, tenant_id=m.tenant_id, limit=500)
    return ok(
        {
            "costs": [
                {
                    "supplier_id": r.supplier_id,
                    "tco_minor": r.tco_minor,
                    "build_up": r.build_up,
                    "fx": r.fx_sources,
                    "stale": r.stale_flag,
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )


@router.get("/missions/{mission_id}/results/risk")
async def risk_results(
    mission_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rows = await rows_for(session, RiskResult, m.id, tenant_id=m.tenant_id, limit=500)
    return ok(
        {
            "risks": [
                {
                    "supplier_id": r.supplier_id,
                    "dimensions": r.dimensions,
                    "composite": r.composite,
                    "band": r.band,
                    "weights_version": r.weights_version,
                }
                for r in rows
            ]
        },
        get_request_id(request),
    )
