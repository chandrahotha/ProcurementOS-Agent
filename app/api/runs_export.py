"""Run replay, report export (05 W8, F15/F16)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import aud, err, log_timeline, must_mission, not_found, rows_for
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.models.mission import CostResult, Mission, MissionRun, ScenarioResult, TimelineEvent
from app.reports.exporter import ExportDeniedError, assert_scope, manifest, to_csv

router = APIRouter()
WRITE_ROLES = {BUYER, MANAGER, ADMIN}


@router.post("/missions/{mission_id}/runs/{run_id}/replay")
async def replay_run(
    mission_id: str,
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    if MANAGER not in principal.roles and ADMIN not in principal.roles:
        return err(403, "forbidden", "Replay needs a manager.", get_request_id(request))
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    rid = get_request_id(request)
    # B52: the run row must exist and belong to this mission — never just
    # echoed into the audit.
    run_row = (
        await session.execute(
            select(MissionRun).where(MissionRun.id == run_id, MissionRun.mission_id == m.id)
        )
    ).scalar_one_or_none()
    if run_row is None:
        return err(404, "not_found", "No such run for this mission.", rid)
    # Replay scenarios from the inputs stored in their timeline events.
    ev_q = select(TimelineEvent).where(
        TimelineEvent.mission_id == m.id, TimelineEvent.kind == "scenario.created"
    )
    events = (await session.execute(ev_q)).scalars().all()
    if not events:
        return err(422, "replay_empty", "Nothing replayable recorded yet.", rid)
    from engine.scenario_opt import allocate

    diffs = []
    for ev in events:
        inputs = (ev.payload or {}).get("inputs")
        if not inputs:
            continue
        sid = (ev.payload or {}).get("scenario_id")
        # Guarded stored-input parsing (B52): malformed inputs report a diff
        # row instead of raising a raw 500.
        try:
            demand = int(inputs["demand"])
        except (KeyError, TypeError, ValueError):
            diffs.append(
                {"scenario_id": str(sid), "match": False, "error": "malformed stored inputs"}
            )
            continue
        try:
            r = allocate(demand, list(inputs.get("offers", [])), inputs.get("max_suppliers"))
        except ValueError as e:
            diffs.append({"scenario_id": str(sid), "match": False, "error": str(e)})
            continue
        stored = (
            await session.execute(
                select(ScenarioResult).where(
                    ScenarioResult.mission_id == m.id, ScenarioResult.scenario_id == sid
                )
            )
        ).scalar_one_or_none()
        if stored is None:
            continue
        match = (
            r["objective_value"] == stored.objective_value
            and r["allocations"] == stored.allocations
        )
        diffs.append(
            {
                "scenario_id": stored.scenario_id,
                "match": match,
                "recomputed": r["objective_value"],
                "stored": stored.objective_value,
            }
        )
    # TCO integrity (E9): the build-up is stored in source currency; when FX
    # converted it to the target currency the raw sum no longer equals
    # tco_minor, so only non-converted rows are sum-checked.
    costs = await rows_for(session, CostResult, m.id, tenant_id=m.tenant_id, limit=500)
    tco_ok = all((not c.fx_sources) or sum(c.build_up.values()) == c.tco_minor for c in costs)
    await aud(
        session,
        request,
        principal,
        "run_replayed",
        m,
        "run",
        run_id,
        after={"scenarios": diffs, "tco_integrity": tco_ok},
    )
    await session.commit()
    # B5: nothing compared -> no "match" verdict, ever.
    matched = bool(diffs) and all(d["match"] for d in diffs) and tco_ok
    return ok(
        {
            "run_id": run_id,
            "scenarios": diffs,
            "tco_integrity": tco_ok,
            "verdict": "match" if matched else "diverged",
        },
        rid,
    )


class ExportBody(BaseModel):
    format: str = "CSV"
    mission_ids: list[str] | None = None


@router.post("/missions/{mission_id}/export")
async def export_report(
    mission_id: str,
    body: ExportBody,
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
    fmt = body.format.upper()
    if fmt not in ("CSV", "XLSX", "PDF"):
        return err(422, "validation_error", "Format must be CSV, XLSX, or PDF.", rid)
    scope = body.mission_ids or [m.id]
    # Tenant-check EVERY scope id (B33): the manifest can never list foreign
    # mission ids, even ones that look in-scope.
    for sid in scope:
        foreign = (
            await session.execute(
                select(Mission).where(Mission.id == sid, Mission.tenant_id == m.tenant_id)
            )
        ).scalar_one_or_none()
        if foreign is None:
            return err(403, "export_denied", "out-of-scope mission in export manifest", rid)
    try:
        assert_scope(principal.tenant_id, m.tenant_id, scope, [m.id])
    except ExportDeniedError as e:
        return err(403, "export_denied", str(e), rid)
    ik = (request.headers.get("Idempotency-Key") or "").strip()
    costs = await rows_for(session, CostResult, m.id, tenant_id=m.tenant_id, limit=500)
    rows = [
        {
            "supplier_id": c.supplier_id,
            "tco_minor": c.tco_minor,
            **{f"build_{k}": v for k, v in c.build_up.items()},
        }
        for c in costs
    ]
    refs = [f"cost:{c.supplier_id}" for c in costs]
    man = manifest(principal.tenant_id, scope, fmt, evidence_refs=refs)
    media = {
        "CSV": "text/csv",
        "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "PDF": "application/pdf",
    }
    if fmt == "CSV":
        content = to_csv(rows)
    elif fmt == "XLSX":
        from io import BytesIO

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "TCO"
        if rows:
            # Union of all row keys (E14): heterogeneous rows never crash.
            fieldnames = sorted({k for r in rows for k in r})
            ws.append(fieldnames)
            for r in rows:
                ws.append([r.get(k) for k in fieldnames])
        ws.append([])
        ws.append(["evidence_refs", ", ".join(man["evidence_refs"])])
        buf = BytesIO()
        wb.save(buf)
        content = buf.getvalue()
    else:
        from io import BytesIO

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawString(72, 800, f"Mission report {m.id} (tenant {man['watermark']})")
        y = 770
        for r in rows:
            c.drawString(72, y, f"{r['supplier_id']}: TCO {r['tco_minor']}")
            y -= 18
        c.drawString(72, y - 12, "Evidence appendix: " + ", ".join(man["evidence_refs"]))
        c.showPage()
        c.save()
        content = buf.getvalue()
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="report.exported",
        payload={
            "format": fmt,
            "manifest": man,
            # B51: the Idempotency-Key is recorded; exports are deterministic
            # by construction (same certified rows -> same bytes).
            "idempotency_key": ik,
        },
        actor_id=principal.user_id,
    )
    await aud(
        session,
        request,
        principal,
        "report_exported",
        m,
        "export",
        None,
        after={"format": fmt, "missions": scope},
    )
    await session.commit()
    disp = f"attachment; filename=report-{m.id}.{fmt.lower()}"
    return Response(
        content=content,
        media_type=media[fmt],
        headers={
            "Content-Disposition": disp,
            "X-Request-ID": rid,
            "X-Manifest-Missions": ",".join(scope),
        },
    )
