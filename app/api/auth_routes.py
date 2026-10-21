"""Real auth over HTTP: login, me, logout (B-auth).

An email and a password are the only way in. The session token is random,
stored hashed, expiry-bound and revocable; the password is PBKDF2-SHA256
with a per-user salt, and a wrong password is answered exactly like an
unknown email, so the endpoint cannot be used to enumerate accounts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.common import aud, err
from app.auth.deps import Principal, get_principal
from app.auth.login import create_session, verify_password
from app.core.envelope import ok
from app.core.request_id import get_request_id
from app.db import get_session
from app.models.foundation import User

router = APIRouter()


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
async def login(
    body: LoginBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Any:
    rid = get_request_id(request)
    u = (
        await session.execute(select(User).where(User.email == body.email.strip()))
    ).scalar_one_or_none()
    if u is None or not verify_password(body.password, u.password_hash):
        # Same shape for unknown email and wrong password (no user enumeration).
        return err(401, "invalid_credentials", "Email or password is incorrect.", rid)
    if u.status != "active":
        return err(403, "account_disabled", "This account is disabled.", rid)
    row, token = await create_session(
        session,
        tenant_id=u.tenant_id,
        user_id=u.id,
        ip=request.client.host if request.client else "",
    )
    await aud(
        session,
        request,
        Principal(
            user_id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            roles=[],
        ),
        "user_login",
        object_type="session",
        object_id=row.id,
    )
    await session.commit()
    return ok(
        {
            "token": token,
            "token_type": "bearer",
            "expires_in_days": 7,
            "email": u.email,
            "name": u.name,
            "tenant_id": u.tenant_id,
        },
        rid,
    )


@router.get("/auth/me")
async def me(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Any:
    rid = get_request_id(request)
    return ok(
        {
            "user_id": principal.user_id,
            "email": principal.email,
            "roles": principal.roles,
            "tenant_id": principal.tenant_id,
        },
        rid,
    )


@router.post("/auth/logout")
async def logout(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Any:
    from sqlalchemy import select as sel

    from app.auth.login import session_token_digest  # noqa: F401  (digest helper)
    from app.models.foundation import UserSession

    rid = get_request_id(request)
    auth = request.headers.get("Authorization", "")
    _, _, token = auth.partition(" ")
    if token:
        q = await session.execute(
            sel(UserSession).where(UserSession.token_hash == session_token_digest(token.strip()))
        )
        row = q.scalar_one_or_none()
        if row is not None:
            row.revoked = True
    await aud(session, request, principal, "user_logout", object_type="session")
    await session.commit()
    return ok({"logged_out": True}, rid)
