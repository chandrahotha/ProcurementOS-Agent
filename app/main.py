"""ProcurementOS-Agent API — standalone mission agent.

Binding docs: prerequisite-docs/ (product brain, source of truth).
Isolation: own schema pos_*, own buckets/queues; no sibling calls.
"""

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    analysis,
    approvals_actions,
    auth_routes,
    evidence,
    misc,
    missions,
    plans_tasks,
    runs_export,
    scenarios,
)
from app.core.config import settings
from app.core.envelope import Meta
from app.core.ratelimit import RateLimitMiddleware
from app.core.request_id import RequestIDMiddleware, get_request_id
from app.db import get_session

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
app.add_middleware(RateLimitMiddleware)

for router in (
    missions.router,
    plans_tasks.router,
    evidence.router,
    analysis.router,
    scenarios.router,
    approvals_actions.router,
    runs_export.router,
    auth_routes.router,
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


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Binding envelope for malformed bodies too (B31): 422 carries the same
    error envelope + request_id as every other failure."""
    rid = get_request_id(request)

    def _jsonable(e: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in e.items():
            if k == "url":
                continue
            if k == "ctx" and isinstance(v, dict):
                out[k] = {ik: str(iv) for ik, iv in v.items()}
            else:
                out[k] = v
        return out

    details = [_jsonable(e) for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Invalid request body.",
                "details": details,
            },
            "request_id": rid,
            "meta": Meta(request_id=rid, version=settings.api_version).model_dump(),
        },
    )


async def _ping_db(session: Any) -> bool:
    """Lightweight DB probe via the request's session (test overrides apply)."""
    from sqlalchemy import text

    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _ping_redis() -> bool:
    try:
        from worker.queue import ping_redis

        return bool(await ping_redis())
    except Exception:
        return False


@app.get("/healthz")
async def healthz(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    rid = get_request_id(request)
    db_ok = await _ping_db(session)
    redis_ok = await _ping_redis()
    # 503 only when the DB is down (compose healthcheck gates on this).
    # Redis down is reported as a boolean — the API stays alive but ops can
    # alert on it; unit/e2e environments intentionally run without redis.
    status = "ok" if db_ok else "unhealthy"
    code = 200 if db_ok else 503
    return JSONResponse(
        status_code=code,
        content={
            "data": {
                "status": status,
                "version": settings.api_version,
                "db": db_ok,
                "redis": redis_ok,
            },
            "meta": {"request_id": rid, "version": settings.api_version},
        },
    )


@app.get(f"{API_PREFIX}/health")
async def api_health(
    request: Request, session: AsyncSession = Depends(get_session)
) -> JSONResponse:
    rid = get_request_id(request)
    db_ok = await _ping_db(session)
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "data": {"status": "ok" if db_ok else "unhealthy", "db": db_ok},
            "meta": {"request_id": rid, "version": settings.api_version},
        },
    )
