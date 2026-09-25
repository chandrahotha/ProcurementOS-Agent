"""ProcurementOS-Agent API — standalone mission agent.

Binding docs: prerequisite-docs/ (product brain, source of truth).
Isolation: own schema pos_*, own buckets/queues; no sibling calls.
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    analysis,
    approvals_actions,
    evidence,
    misc,
    missions,
    plans_tasks,
    runs_export,
    scenarios,
)
from app.core.config import settings
from app.core.envelope import Meta
from app.core.request_id import RequestIDMiddleware, get_request_id

API_PREFIX = "/api/v1"

app = FastAPI(title="ProcurementOS-Agent", version="0.1.0")
# Browser origin only; the web app never talks to a third-party host.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Manifest-Missions", "Content-Disposition"],
)
app.add_middleware(RequestIDMiddleware)

for router in (
    missions.router,
    plans_tasks.router,
    evidence.router,
    analysis.router,
    scenarios.router,
    approvals_actions.router,
    runs_export.router,
    misc.router,
):
    app.include_router(router, prefix=API_PREFIX)
    # /cases/* mirrors /missions/* for template compatibility (same handlers).
    app.include_router(router, prefix=f"{API_PREFIX}/cases")


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = get_request_id(request)
    if isinstance(exc, HTTPException):
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found"}.get(
            exc.status_code, f"http_{exc.status_code}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": code, "message": str(exc.detail), "details": None},
                "request_id": rid,
                "meta": Meta(request_id=rid, version=settings.api_version).model_dump(),
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "internal_error", "message": "Unexpected error.", "details": None},
            "request_id": rid,
            "meta": Meta(request_id=rid, version=settings.api_version).model_dump(),
        },
    )


async def _http_envelope(request: Request, status: int, detail: Any) -> JSONResponse:
    """Binding envelope for every HTTP error incl. auth failures (05 add-on)."""
    rid = get_request_id(request)
    code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 410: "gone"}.get(
        status, f"http_{status}"
    )
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": str(detail), "details": None},
            "request_id": rid,
            "meta": Meta(request_id=rid, version=settings.api_version).model_dump(),
        },
    )


@app.exception_handler(HTTPException)
async def fastapi_http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return await _http_envelope(request, exc.status_code, exc.detail)


@app.exception_handler(StarletteHTTPException)
async def starlette_http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return await _http_envelope(request, exc.status_code, exc.detail)


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
