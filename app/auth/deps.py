"""Auth dependencies.

Prod: OIDC Bearer JWT (validated against OIDC_ISSUER/AUDIENCE).
Dev/test: when no OIDC_ISSUER is configured, accept `Test <token>` or
`Bearer <api_token>` mapped to pos_user.api_token (documented dev fallback;
CI uses it for golden tests). Never accept the fallback when OIDC is configured.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import roles as R
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


async def _dev_principal(authorization: str, session: AsyncSession) -> Principal | None:
    if settings.oidc_issuer:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme not in ("Bearer", "Test") or not token:
        return None
    q = await session.execute(select(User).where(User.api_token == token.strip()))
    user = q.scalar_one_or_none()
    if user is None:
        return None
    # Roles come from workspace membership in Phase 2; dev fallback: email-prefix map.
    return Principal(
        user_id=user.id, tenant_id=user.tenant_id, email=user.email, roles=_roles_for(user)
    )


def _roles_for(user: User) -> list[str]:
    prefix = user.email.split("@")[0].lower()
    if prefix.startswith("daniel"):
        return [R.MANAGER, R.BUYER]
    if prefix.startswith("fatima"):
        return [R.FINANCE]
    if prefix.startswith("chen"):
        return [R.COMPLIANCE]
    if prefix.startswith("admin"):
        return [R.ADMIN]
    return [R.BUYER]


async def _membership_roles(session: AsyncSession, user: User) -> list[str]:
    """Union of lane roles from workspace memberships; Buyer default."""
    q = await session.execute(select(Workspace).where(Workspace.tenant_id == user.tenant_id))
    found: set[str] = set()
    for ws in q.scalars().all():
        for m in ws.members or []:
            if m.get("user_id") == user.id:
                found.update(m.get("roles", []))
    return sorted(found) or [R.BUYER]


async def _oidc_principal(authorization: str, session: AsyncSession) -> Principal:
    scheme, _, token = authorization.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing credentials")
    try:
        claims = verify_bearer(token.strip(), settings.oidc_issuer, settings.oidc_audience)
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
    principal = await _dev_principal(authorization, session)
    if principal is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return principal


def require_roles(*allowed: str) -> Callable[[Principal], Awaitable[Principal]]:
    async def checker(principal: Principal = Depends(get_principal)) -> Principal:
        if not set(principal.roles) & set(allowed):
            raise HTTPException(status_code=403, detail="Forbidden for role")
        return principal

    return checker


def require_lane(lane: str) -> Callable[[Principal], Awaitable[Principal]]:
    allowed = R.LANE_ROLES.get(lane, [])
    return require_roles(*allowed)
