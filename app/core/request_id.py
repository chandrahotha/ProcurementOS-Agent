"""request_id propagation: inbound X-Request-ID or generated uuid7-ish; echoed back."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIDMiddleware(BaseHTTPMiddleware):
    header = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get(self.header) or f"req_{uuid.uuid4().hex[:24]}"
        request.state.request_id = rid
        response = await call_next(request)
        response.headers[self.header] = rid
        return response


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")
