"""Evidence spans: list, record (extraction/manual entry), correct (05 W2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import aud, err, log_timeline, must_mission, not_found
from app.auth.deps import Principal, get_principal
from app.auth.roles import ADMIN, BUYER, MANAGER
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.ingest.instructions import planning_inputs_clean, scan
from app.models.foundation import EvidenceSpan

router = APIRouter()
WRITE_ROLES = {BUYER, MANAGER, ADMIN}


class SpanIn(BaseModel):
    document_id: str
    field_name: str
    field_value: str
    quoted_text: str = ""
    page: int | None = None
    paragraph: int | None = None
    confidence: float = 0.0


class CorrectBody(BaseModel):
    field_value: str
    reason: str = ""


def _dto(s: EvidenceSpan) -> dict[str, Any]:
    return {
        "id": s.id,
        "document_id": s.document_id,
        "field_name": s.field_name,
        "field_value": s.field_value,
        "quoted_text": s.quoted_text,
        "page": s.page,
        "paragraph": s.paragraph,
        "confidence": s.confidence,
        "extractor": s.extractor,
        "extractor_version": s.extractor_version,
        "instruction_flag": s.instruction_flag,
    }


@router.get("/missions/{mission_id}/evidence")
async def list_evidence(
    mission_id: str,
    request: Request,
    flagged: bool | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    q = select(EvidenceSpan).where(EvidenceSpan.mission_id == m.id)
    if flagged is not None:
        q = q.where(EvidenceSpan.instruction_flag.is_(flagged))
    spans = (await session.execute(q)).scalars().all()
    return ok({"spans": [_dto(s) for s in spans]}, get_request_id(request))


@router.post("/missions/{mission_id}/evidence/spans")
async def record_spans(
    mission_id: str,
    body: list[SpanIn],
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Record extraction candidates or manual entries (outage fallback)."""
    rid = get_request_id(request)
    if not set(principal.roles) & WRITE_ROLES:
        return err(403, "forbidden", "Forbidden for role.", rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    out = []
    for cand in body:
        flag = scan(cand.quoted_text or cand.field_value)
        s = EvidenceSpan(
            tenant_id=m.tenant_id,
            mission_id=m.id,
            document_id=cand.document_id,
            field_name=cand.field_name,
            field_value=cand.field_value,
            quoted_text=cand.quoted_text,
            page=cand.page,
            paragraph=cand.paragraph,
            confidence=cand.confidence,
            instruction_flag=flag["flagged"],
        )
        session.add(s)
        await session.flush()
        out.append(_dto(s))
        if flag["flagged"]:
            await aud(
                session,
                request,
                principal,
                "hostile_span_quarantined",
                m,
                "evidence_span",
                s.id,
                reason=f"patterns: {flag['hits']}",
            )
    n_clean = len(
        planning_inputs_clean(
            [
                {"field_name": s["field_name"], "instruction_flag": s["instruction_flag"]}
                for s in out
            ]
        )
    )
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="document.extracted",
        payload={"spans": len(out), "planning_inputs": n_clean},
        actor_id=principal.user_id,
    )
    await session.commit()
    return ok({"spans": out}, rid)


@router.patch("/missions/{mission_id}/evidence/{span_id}")
async def correct_span(
    mission_id: str,
    span_id: str,
    body: CorrectBody,
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    if not set(principal.roles) & WRITE_ROLES:
        return err(403, "forbidden", "Forbidden for role.", rid)
    try:
        m = await must_mission(session, principal, mission_id)
    except Exception as e:
        return not_found(request, e)
    q = await session.execute(
        select(EvidenceSpan).where(
            EvidenceSpan.id == span_id,
            EvidenceSpan.mission_id == m.id,
            EvidenceSpan.tenant_id == m.tenant_id,
        )
    )
    s = q.scalar_one_or_none()
    if s is None:
        return err(404, "not_found", "No such span.", rid)
    before = {"field_value": s.field_value}
    s.field_value = body.field_value
    await aud(
        session,
        request,
        principal,
        "evidence_corrected",
        m,
        "evidence_span",
        s.id,
        after={"field_value": body.field_value, "before": before},
        reason=body.reason or None,
    )
    await log_timeline(
        session,
        tenant_id=m.tenant_id,
        mission_id=m.id,
        kind="evidence.corrected",
        payload={"span_id": s.id},
        actor_id=principal.user_id,
    )
    await session.commit()
    return ok({**_dto(s), "reanalysis_recommended": True}, rid)
