"""Real credential login: PBKDF2-SHA256 password verification + session tokens.

Tokens are random (secrets), hashed at rest, expiry-bound, revocable. The
dev-token fallback stays as a dev/test convenience; OIDC remains the prod
SSO path. Stdlib only — no new dependency.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.foundation import User, UserSession

SESSION_DAYS = 7
PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def session_token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def as_utc(value: datetime | None) -> datetime | None:
    """Read a stored timestamp as an aware UTC datetime.

    A `DateTime(timezone=True)` column is timezone-aware on Postgres and
    naive on SQLite, which does not store an offset. Comparing the two
    raises `TypeError: can't compare offset-naive and offset-aware
    datetimes` — which is what happened to every session lookup on the
    dev and test engine, and therefore to the whole credential-login
    path, which no test had exercised.

    A naive stored value is read as UTC, which is what it was written as:
    every timestamp this module stores is `datetime.now(UTC)`.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def create_session(
    session: AsyncSession, *, tenant_id: str, user_id: str, ip: str = ""
) -> tuple[UserSession, str]:
    token = secrets.token_urlsafe(32)
    row = UserSession(
        tenant_id=tenant_id,
        user_id=user_id,
        token_hash=session_token_digest(token),
        expires_at=datetime.now(UTC) + timedelta(days=SESSION_DAYS),
        created_ip=ip[:64],
    )
    session.add(row)
    await session.flush()
    return row, token


async def principal_from_session(
    session: AsyncSession, token: str
) -> tuple[User, UserSession] | None:
    """Resolve a bearer token to a live, unexpired, unrevoked session."""
    q = await session.execute(
        select(UserSession).where(UserSession.token_hash == session_token_digest(token))
    )
    row = q.scalar_one_or_none()
    if row is None or row.revoked:
        return None
    expires_at = as_utc(row.expires_at)
    if expires_at is not None and expires_at < datetime.now(UTC):
        return None
    u = await session.get(User, row.user_id)
    if u is None or u.status != "active":
        return None
    return u, row


async def revoke_session(session: AsyncSession, token: str) -> bool:
    q = await session.execute(
        select(UserSession).where(UserSession.token_hash == session_token_digest(token))
    )
    row = q.scalar_one_or_none()
    if row is None:
        return False
    row.revoked = True
    await session.flush()
    return True
