"""ProcurementOS-Agent API — standalone mission agent.

Binding docs: prerequisite-docs/ (product brain, source of truth).
Isolation: own schema pos_*, own buckets/queues; no sibling calls.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.envelope import Meta
from app.core.request_id import RequestIDMiddleware, get_request_id

API_PREFIX = "/api/v1"

app = FastAPI(title="ProcurementOS-Agent", version="0.1.0")
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = get_request_id(request)
    # Safe message only; full traceback goes to server logs, never the client.
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "internal_error", "message": "Unexpected error.", "details": None},
            "request_id": rid,
            "meta": Meta(request_id=rid, version=settings.api_version).model_dump(),
        },
    )


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, Any]:
    rid = get_request_id(request)
    return {
        "data": {"status": "ok", "version": settings.api_version},
        "meta": {"request_id": rid, "version": settings.api_version},
    }


@app.get(f"{API_PREFIX}/health")
async def api_health(request: Request) -> dict[str, Any]:
    rid = get_request_id(request)
    return {"data": {"status": "ok"}, "meta": {"request_id": rid, "version": settings.api_version}}


# Routers for later phases (missions, plans, tasks, evidence, results,
# scenarios, negotiation, approvals, actions, runs, export, timeline)
# are mounted here as each phase lands. Phase 0 intentionally ships
# only health + envelope + request_id so CI/local runbook goes green.
