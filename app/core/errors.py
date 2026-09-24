"""Safe error helpers: never leak stack/schema internals to clients."""

from typing import Any

from fastapi.responses import JSONResponse

from app.core.envelope import fail


def error_response(
    status: int,
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(status_code=status, content=fail(code, message, request_id, details))
