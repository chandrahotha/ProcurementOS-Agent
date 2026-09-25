"""Per-IP fixed-window rate limiting on write endpoints (B30).

No external dependency: an in-process fixed-window counter per (IP, window).
Per-process scope: with multiple workers the effective limit multiplies by
the replica count — acceptable as a first control; approval/execute paths
re-verify quorum server-side regardless of what the limiter allows.
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
WINDOW_S = 60.0
LIMIT = 120


class RateLimitMiddleware(BaseHTTPMiddleware):
    _counts: dict[tuple[str, int], int] = defaultdict(int)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method not in WRITE_METHODS:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        window = int(time.monotonic() // WINDOW_S)
        counts = RateLimitMiddleware._counts
        if len(counts) > 10_000:
            cutoff = window - 2
            for k in [k for k in counts if k[1] < cutoff]:
                counts.pop(k, None)
        counts[(client, window)] += 1
        if counts[(client, window)] > LIMIT:
            rid = getattr(request.state, "request_id", "")
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests; retry shortly.",
                        "details": None,
                    },
                    "request_id": rid,
                },
            )
        return await call_next(request)
