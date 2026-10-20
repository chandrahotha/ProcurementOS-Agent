"""Issue 3: OIDC JWKS validation — mint real RS256 tokens, no network."""

import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import oidc
from app.auth.deps import get_principal
from app.core.config import settings as app_settings
from app.models.base import Base
from app.models.foundation import User, Workspace

ISSUER = "https://idp.syn.example"
AUD = "pos-api"


def _b64(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture()
def keys():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key().public_numbers()
    pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    jwk = {
        "kty": "RSA",
        "kid": "k1",
        "use": "sig",
        "alg": "RS256",
        "n": _b64(pub.n),
        "e": _b64(pub.e),
    }
    return pem, jwk


@pytest.fixture()
def fake_idp(monkeypatch, keys):
    pem, jwk = keys

    def fake_get(url, timeout=10):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                if url.endswith(".well-known/openid-configuration"):
                    return {"jwks_uri": ISSUER + "/jwks"}
                return {"keys": [jwk]}

        return R()

    monkeypatch.setattr("httpx.get", fake_get)
    monkeypatch.setattr(app_settings, "oidc_issuer", ISSUER)
    monkeypatch.setattr(app_settings, "oidc_audience", AUD)
    oidc.clear_cache()
    return pem


async def _seed(sub):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    mk = async_sessionmaker(engine, expire_on_commit=False)
    async with mk() as s:
        # `tok-op` is a synthetic token for an in-memory test database; it
        # authenticates nobody and exists only to give the row a handle.
        u = User(
            tenant_id="t1",
            email="op@x.io",
            name="Op",
            api_token="tok-op",  # noqa: S106 - synthetic test value
            oidc_sub=sub,
        )
        s.add(u)
        await s.flush()
        s.add(
            Workspace(
                tenant_id="t1", name="W", members=[{"user_id": u.id, "roles": ["FinanceReviewer"]}]
            )
        )
        await s.commit()
        uid = u.id
    return mk, uid


def _tok(pem, sub="sub-1", aud=AUD, exp_in=300, kid="k1"):
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "aud": aud, "iss": ISSUER, "iat": now, "exp": now + exp_in},
        pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


async def test_valid_token_maps_roles(fake_idp):
    mk, uid = await _seed("sub-1")
    async with mk() as s:
        p = await get_principal(f"Bearer {_tok(fake_idp)}", s)
    assert (p.user_id, p.tenant_id) == (uid, "t1")
    assert p.roles == ["FinanceReviewer"]


async def test_expired_wrongaud_unknownkid_badsig_rejected(fake_idp, keys):
    pem, jwk = keys
    mk, _ = await _seed("sub-1")
    bad = [
        _tok(pem, exp_in=-3600),  # expired an hour ago (leeway only covers skew)
        _tok(pem, aud="someone-else"),  # wrong audience
        _tok(pem, kid="nope"),  # unknown kid
        _tok(pem)[:-4] + "abcd",  # tampered signature
        _tok(pem, sub="ghost"),  # unknown subject
    ]
    async with mk() as s:
        for t in bad:
            with pytest.raises(HTTPException) as ei:
                await get_principal(f"Bearer {t}", s)
            assert ei.value.status_code == 401


async def test_dev_fallback_dead_when_oidc_configured(fake_idp):
    mk, _ = await _seed("sub-1")
    async with mk() as s:
        with pytest.raises(HTTPException) as ei:
            await get_principal("Bearer tok-op", s)
        assert ei.value.status_code == 401
