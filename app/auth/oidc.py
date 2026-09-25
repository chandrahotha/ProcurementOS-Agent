"""OIDC Bearer validation via JWKS (08 section 2).

Fails closed: unknown issuer config, bad signature, wrong audience,
or expired token all raise AuthError (mapped to 401 upstream).
JWKS responses are cached briefly; key rollover is picked up on TTL expiry.

Uses PyJWT (RS256). python-jose was dropped because it pins `ecdsa`,
which carries an unfixable advisory (see docs/adr/0002-pyjwt.md).
"""

from __future__ import annotations

import time
from typing import Any, cast

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import DecodeError, ExpiredSignatureError, InvalidTokenError

JWKS_TTL_S = 600

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class AuthError(Exception):
    pass


def _get(url: str) -> dict[str, Any]:
    try:
        r = httpx.get(url, timeout=10)
        r.raise_for_status()
        return dict(r.json())
    except Exception as e:
        raise AuthError(f"identity metadata unreachable: {e}") from e


def jwks_for(issuer: str) -> dict[str, Any]:
    now = time.time()
    hit = _cache.get(issuer)
    if hit and hit[0] > now:
        return hit[1]
    conf = _get(issuer.rstrip("/") + "/.well-known/openid-configuration")
    uri = conf.get("jwks_uri")
    if not uri:
        raise AuthError("issuer metadata has no jwks_uri")
    keys = _get(str(uri))
    _cache[issuer] = (now + JWKS_TTL_S, keys)
    return keys


def verify_bearer(token: str, issuer: str, audience: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except DecodeError as e:
        raise AuthError(f"malformed token: {e}") from e
    keys = jwks_for(issuer)
    kid = header.get("kid")
    entry = next((k for k in keys.get("keys", []) if k.get("kid") == kid), None)
    if entry is None:
        raise AuthError("signing key not in JWKS (unknown kid)")
    try:
        # from_jwk's stub includes private-key types, but a JWKS only
        # carries public material; cast is honest and runtime-checked below.
        key = cast("Any", RSAAlgorithm.from_jwk(entry))
    except Exception as e:
        raise AuthError(f"unsupported signing key: {e}") from e
    try:
        claims = jwt.decode(
            key=key,
            jwt=token,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
        )
        return dict(claims)
    except ExpiredSignatureError as e:
        raise AuthError("token expired") from e
    except InvalidTokenError as e:
        # Covers wrong audience/issuer, bad signature, bad claims shape.
        raise AuthError(f"claim mismatch: {e}") from e


def clear_cache() -> None:
    _cache.clear()
