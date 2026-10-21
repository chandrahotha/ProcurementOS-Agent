"""Auth dependencies.

There are exactly two ways in, and no third:

* **OIDC** (production). A Bearer JWT validated against
  `OIDC_ISSUER`/`OIDC_AUDIENCE` and resolved to a user by `oidc_sub`.
* **A session** (everywhere else). A bearer token minted by
  `POST /api/v1/auth/login` from an email and a password. The token is
  random, stored hashed, expiry-bound and revocable.

There is no developer token, no email-derived token, and no way to
authenticate without a credential that was issued to somebody who
proved they hold one. The app refuses to boot in production without an
OIDC issuer (bugs/01-backend.md B21).

Roles come from workspace membership, never from the email (B23).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import roles as R
from app.auth.login import principal_from_session
from app.auth.oidc import AuthError, verify_bearer
from app.core.config import settings
from app.db import get_session
from app.models.foundation import User, Workspace


@dataclass
class Principal:
    user_id: str
    tenant_id: str
    email: str
    roles: list[str]


# Per-process TTL cache for membership roles (B41): the workspace scan would
# otherwise run on every authenticated request. Role changes reflect within
# the TTL window; lane-critical paths re-check via require_roles/decide.
_ROLES_TTL_S = 30.0
_roles_cache: dict[tuple[str, str], tuple[float, list[str]]] = {}


async def _membership_roles(session: AsyncSession, user: User) -> list[str]:
    """Union of lane roles from workspace memberships; Buyer default.

    Roles never derive from the email prefix (B23)."""
    key = (user.tenant_id, user.id)
    now = time.monotonic()
    hit = _roles_cache.get(key)
    if hit is not None and now - hit[0] < _ROLES_TTL_S:
        return hit[1]
    q = await session.execute(select(Workspace).where(Workspace.tenant_id == user.tenant_id))
    found: set[str] = set()
    for ws in q.scalars().all():
        for m in ws.members or []:
            if m.get("user_id") == user.id:
                found.update(m.get("roles", []))
    roles = sorted(found) or [R.BUYER]
    _roles_cache[key] = (now, roles)
    return roles


async def _oidc_principal(authorization: str, session: AsyncSession) -> Principal:
    scheme, _, token = authorization.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing credentials")
    try:
        # The JWKS fetch can block for seconds when the IdP is slow or down:
        # run it off the event loop so auth latency never starves requests (B24).
        claims = await asyncio.to_thread(
            verify_bearer, token.strip(), settings.oidc_issuer, settings.oidc_audience
        )
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    sub = str(claims.get("sub", ""))
    q = await session.execute(select(User).where(User.oidc_sub == sub))
    user = q.scalar_one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="Unknown subject")
    return Principal(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        roles=await _membership_roles(session, user),
    )


async def get_principal(
    authorization: str = Header(default=""),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    if settings.oidc_issuer:
        return await _oidc_principal(authorization, session)
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing credentials")
    scheme, _, token = authorization.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing credentials")
    # A session token from POST /auth/login: live, unexpired, unrevoked.
    found = await principal_from_session(session, token.strip())
    if found is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user, _row = found
    return Principal(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        roles=await _membership_roles(session, user),
    )


def require_roles(*allowed: str) -> Callable[[Principal], Awaitable[Principal]]:
    async def checker(principal: Principal = Depends(get_principal)) -> Principal:
        if not set(principal.roles) & set(allowed):
            raise HTTPException(status_code=403, detail="Forbidden for role")
        return principal

    return checker


def require_lane(lane: str) -> Callable[[Principal], Awaitable[Principal]]:
    allowed = R.LANE_ROLES.get(lane, [])
    return require_roles(*allowed)
