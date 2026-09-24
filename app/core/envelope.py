"""Binding response envelope per prerequisite-docs/05 (CROSS-CHECK ADD-ON).

Success: {"data": ..., "meta": {"request_id": ..., "version": "v1"}}
Error:   {error:{code,message,details}, request_id, meta:{version}}
request_id is present on EVERY response incl. 401/403/422/409.
"""

from typing import Any

from pydantic import BaseModel

from app.core.config import settings


class Meta(BaseModel):
    request_id: str
    version: str = settings.api_version


def ok(data: Any, request_id: str) -> dict[str, Any]:
    return {
        "data": data,
        "meta": Meta(request_id=request_id).model_dump(),
    }


def fail(
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {"code": code, "message": message, "details": details},
        "request_id": request_id,
        "meta": Meta(request_id=request_id).model_dump(),
    }
