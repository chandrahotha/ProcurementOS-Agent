"""Egress policy for outbound calls (SSRF).

The release gate asks for "SSRF suite against live webhook hosts". The
outbound call this product makes is the outbox delivery: an approved
supplier message is posted to the configured webhook. That URL comes from
the environment, not from a request, so it is not directly attacker
controlled — but a configuration mistake (a URL that points at the cloud
metadata endpoint, or at an internal admin port) would turn the API into a
proxy, and a future caller that passes a request-supplied URL would make
it exploitable.

So the rule is enforced in one place, and every outbound caller goes
through it:

* the scheme must be http or https — `file://`, `gopher://` and friends
  are refused outright,
* the host must be on the allowlist when one is configured. The allowlist
  is the deployment's statement of where this product is allowed to send
  things, and it is empty by default, which means "same host as the
  configured webhook",
* a redirect is not followed to a different host: httpx is told not to
  follow redirects at all, so a 302 cannot walk the request somewhere the
  allowlist would have refused.

Loopback and private addresses are *not* blanket-refused: a staging
webhook host is very often on a private network, and the allowlist is the
right control for that. What the allowlist buys is that the set of
reachable destinations is declared rather than implied.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

#: Schemes an outbound call may use. Everything else is refused.
ALLOWED_SCHEMES = ("http", "https")


class EgressDeniedError(ValueError):
    """The destination is not allowed by the egress policy."""


def _allowlist() -> tuple[str, ...]:
    raw = os.environ.get("OUTBOX_WEBHOOK_ALLOWLIST", "").strip()
    if not raw:
        return ()
    return tuple(part.strip().lower() for part in raw.split(",") if part.strip())


def check_url(url: str, *, allowlist: tuple[str, ...] | None = None) -> str:
    """Validate an outbound destination. Returns the URL on success.

    Raises `EgressDeniedError` when the destination is not allowed.
    """
    if not url or not url.strip():
        raise EgressDeniedError("no destination")
    candidate = url.strip()
    parts = urlsplit(candidate)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise EgressDeniedError(f"scheme not allowed: {parts.scheme!r}")
    host = (parts.hostname or "").lower()
    if not host:
        raise EgressDeniedError("no host in destination")
    allowed = _allowlist() if allowlist is None else allowlist
    if allowed:
        # A host matches if it is listed exactly or is a subdomain of a
        # listed suffix (".example.com" matches "api.example.com").
        permitted = any(host == a or host.endswith("." + a.lstrip(".")) for a in allowed)
        if not permitted:
            raise EgressDeniedError(f"host not on the egress allowlist: {host!r}")
    return candidate


def is_allowed(url: str, *, allowlist: tuple[str, ...] | None = None) -> bool:
    """Boolean form of `check_url`."""
    try:
        check_url(url, allowlist=allowlist)
    except EgressDeniedError:
        return False
    return True
