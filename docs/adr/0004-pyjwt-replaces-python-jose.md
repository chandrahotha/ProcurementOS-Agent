# ADR-0004 — JWT validation moved from python-jose to PyJWT

- Status: Accepted
- Date: 2026-09-24

## Context

Phase 0 chose `python-jose[cryptography]` for RS256/JWKS validation. The
dependency audit (issue #7) flagged `ecdsa` — an unfixable advisory with
no patched release — pulled in by python-jose. Auth is security-critical;
an unpatchable transitive in the token path is not acceptable.

## Decision

Replace python-jose with `pyjwt[crypto]` in `app/auth/oidc.py`. Same
guarantees: RS256 only, kid match against the issuer's JWKS, audience
and issuer claims enforced, expiry enforced, unknown/missing kid fails
closed, JWKS cached with a short TTL for key rollover. Tests mint real
RSA keys locally and cover valid, expired, wrong-audience, unknown-kid,
tampered-signature, and unknown-subject tokens.

## Consequences

- The `ecdsa` advisory leaves the tree; `pip-audit` is clean.
- One behavior note: PyJWT is stricter about `sub` handling — unknown
  subjects fail closed, which is what we want anyway.

## Brain refs

- `08_SECURITY_AND_COMPLIANCE.md` §2 (controls) — library not pinned by
  the brain; recorded because the token path is security-critical.

## Rollback

Restore python-jose and accept the ecdsa finding with a dated note —
not recommended while the advisory has no fix.
