# ADR 0012 — One credential: an email and a password, and nothing else

- **Status:** accepted
- **Date:** 2026-10-21
- **Related:** ADR 0001, ADR 0009; `bugs/01-backend.md` B21, B22, B23

## Context

The product had two ways to authenticate a request, and one of them did not
need a secret.

* **OIDC.** A Bearer JWT validated against `OIDC_ISSUER`/`OIDC_AUDIENCE` and
  resolved to a user by `oidc_sub`. The production path.
* **A developer token.** When no issuer was configured, any `Bearer <token>`
  was matched against the SHA-256 digest stored in `pos_user.api_token`. The
  seeded value was `sha256("dev-" + email)`.

The second path was fenced — it was unreachable the moment an issuer was
configured, and the app refuses to boot in production without one — and it
was hashed at rest rather than stored in plaintext. But it was still a
credential that everybody in the repository, and anybody who had read the
seed, could mint for themselves: the digest of a seeded email address is a
function of that address and the fixed string `dev-`. It is not a secret
that was kept secret; it is a formula.

By the time the credential login was implemented, the developer token had
also become redundant. `POST /api/v1/auth/login` takes an email and a
password, verifies the password against a salted PBKDF2-SHA256 hash, and
mints a session token that is random, stored hashed, expiry-bound and
revocable. That path was newer, stronger, and already exercised by the
tests. The developer token was the weaker of two ways in, kept alive only by
being convenient.

The brain (`05_WORKFLOWS_AND_API.md`) asks for OIDC Bearer JWT and server-side
membership checks on every route. It never asked for the developer token.
Removing it moves the implementation towards the specification, not away
from it.

## Decision

**There is one credential, and it is a password.**

- `pos_user.api_token` is dropped (`alembic` `pos_007`). A column that looks
  like a credential store and is not one is worse than no column.
- The developer-token path is removed from `app/auth/deps.py`. A request is
  authenticated either by an OIDC JWT (when an issuer is configured) or by a
  session token minted from an email and a password.
- The web app signs in with an email and a password. The token box on Mission
  Control and the token form on the login screen are gone; the login screen
  offers the seeded personas as a one-click shortcut that fills the demo
  password in, so the demo stays one click deep.
- The tests sign in through the login endpoint, so the suite exercises the
  same credential path a person takes.
- The seed writes a password hash and nothing else.

## Consequences

- **A credential nobody can compute.** A session token is 32 bytes of
  `secrets.token_urlsafe`; the password is only ever stored as a salted
  PBKDF2 hash. There is no longer a path into the API that can be derived
  from an email address.
- **One path to test.** The suite no longer needs a second authentication
  mode to cover the "dev" case, so the credential path that production will
  actually use is the one the tests exercise.
- **The seeded demo password is published.** `syn-Demo-2026!` is in the
  runbook, the README and the login screen. That is deliberate — it is
  synthetic, it authenticates nothing outside the local demo database, and
  the seed refuses to run against a non-synthetic one — but it does mean the
  demo tenant has no meaningful confidentiality, and must never be pointed at
  anything real.
- **The migration is reversible.** `pos_007` re-adds the column on
  downgrade, so a deployment that needs it is not stuck.
