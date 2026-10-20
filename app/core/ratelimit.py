"""Write-endpoint rate limiting (B30).

Two independent fixed-window counters, because one counter is wrong in two
different directions:

* **per principal** — one authenticated user cannot spend the whole
  tenant's write budget. This is the limit that matters for a real
  deployment: behind a reverse proxy every request arrives with the
  *proxy's* IP, so an IP-only counter collapses the entire user base into
  one bucket and the noisiest user throttles everybody.
* **per client address** — an unauthenticated flood, or one that rotates
  bearer tokens to dodge the per-principal limit, is still bounded.

The per-principal key is a short digest of the Authorization header. It is
never the token itself, and an absent header produces the "anonymous" key,
so unauthenticated traffic shares one bucket per address.

`X-Forwarded-For` is honoured only when the deployment says a proxy is in
front (`TRUSTED_PROXY=true`). Trusting it unconditionally would let any
client forge its address and walk straight past the limit.

Scope is per process: with several workers the effective limit multiplies
by the replica count. That is accepted as a first control — the
approval/execute paths re-verify quorum server-side regardless of what the
limiter allows.
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
WINDOW_S = 60.0

#: Writes per minute, per authenticated principal.
LIMIT = 120

#: Writes per minute, per client address. Higher than the principal
#: limit because one address legitimately fronts many users.
ADDRESS_LIMIT = 600


def _client_address(request: Request) -> str:
    """The address to count against, honouring a trusted proxy."""
    from app.core.config import settings

    if settings.trusted_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _principal_key(request: Request) -> str:
    """A short, non-reversible digest of the caller's credential."""
    header = request.headers.get("authorization", "")
    if not header:
        return "anonymous"
    return hashlib.sha256(header.encode()).hexdigest()[:16]


class RateLimitMiddleware(BaseHTTPMiddleware):
    _counts: dict[tuple[str, str, int], int] = defaultdict(int)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method not in WRITE_METHODS:
            return await call_next(request)
        address = _client_address(request)
        principal = _principal_key(request)
        window = int(time.monotonic() // WINDOW_S)
        counts = RateLimitMiddleware._counts

        if len(counts) > 10_000:
            cutoff = window - 2
            for k in [k for k in counts if k[2] < cutoff]:
                counts.pop(k, None)

        principal_key = (address, principal, window)
        address_key = (address, "*", window)
        counts[principal_key] += 1
        counts[address_key] += 1

        if counts[principal_key] > LIMIT or counts[address_key] > ADDRESS_LIMIT:
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


def reset_rate_limits() -> None:
    """Clear the in-process counters.

    The counters are process-wide state on purpose (the limit has to hold
    across requests), which makes them global state that a test has to be
    able to clear: a suite that makes more than `LIMIT` writes in a minute
    would otherwise start answering 429 to itself.
    """
    RateLimitMiddleware._counts.clear()
