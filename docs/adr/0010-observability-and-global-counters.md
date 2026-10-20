# ADR 0010 — Observability, and the two global counters

- **Status:** accepted
- **Date:** 2026-10-20
- **Related:** release gate "Monitoring + queue/task-age alerts live"

## Context

The release gate said "OpenTelemetry wiring exists; dashboards pending
staging (issue #8)". It did not exist. There was no metrics collection, no
trace, and no dashboard anywhere in the tree — the sentence described an
intention that was never carried out.

Separately, two pieces of process-wide state turned out to be real
production issues, and both were found by the same route: splitting the
giant lifecycle test into phases made the suite make many more requests
than it used to, and the failures that appeared were not test bugs.

**The AI circuit breaker** is a module-level singleton, on purpose: the
provider is a shared dependency, so an outage should stop every caller
from waiting on it. The AGENT-004 test trips it, and it then silenced the
provider for every test that ran afterwards — in an unrelated file.

**The rate limiter** counted by `request.client.host` alone. Behind a
reverse proxy every request arrives with the *proxy's* address, so an
IP-only counter collapses the whole user base into one bucket: the
noisiest user throttles everybody. The same counter is also what made the
split suite answer itself with 429s.

## Decision

**Observability.** Add a dependency-free metrics layer
(`app/core/observe.py`): request count, error count and duration per
route; named counters; and queue depth with the age of the oldest waiting
task. The exposition format is Prometheus text, served from
`/api/v1/ops/metrics` behind an administrator's session. `/api/v1/ops/queue-age`
reports the queue in JSON, and `scripts/task_age.py` is the alert: it
exits non-zero when the oldest waiting task passes the threshold, so it
can run from cron or a probe.

The reason for a queue-age alert specifically: a queue that stops
draining is the failure this product is least able to notice on its own.
Nothing raises, no request fails, the missions just stop moving.

**The rate limiter** now keeps two counters: one per authenticated
principal (120 writes/minute) and one per client address (600
writes/minute). The per-principal limit is what stops one user behind a
NAT from spending everyone else's budget; the per-address limit still
bounds an unauthenticated flood or one that rotates bearer tokens. The
principal key is a short SHA-256 digest of the `Authorization` header,
never the token itself. `X-Forwarded-For` is honoured only when the
deployment says a proxy is in front (`TRUSTED_PROXY=true`), because
trusting it unconditionally would let a client forge its address and walk
straight past the limit.

**Both counters get an explicit reset**, and the test suite resets them
around every test.

## Consequences

- The release gate's monitoring box can be answered with two commands and
  a metrics endpoint, instead of a promise.
- The metrics are per process, the same caveat as the rate limiter: with
  several workers each process counts its own share. Behind a single
  process — the normal deployment for this product — they are exact.
- `TRUSTED_PROXY` is a new environment key, blank by default.
- The rate limit is now per *user* as well as per address. A deployment
  behind a proxy that forgets to set `TRUSTED_PROXY` will still see the
  proxy's address, but the per-principal counter is what the limit is
  really about, and it is correct either way.
- The suite is order-independent again, and the reason is written down
  rather than remembered.

## Brain refs

`prerequisite-docs/08_SECURITY_AND_COMPLIANCE.md` (rate limiting is a
control; a control that punishes the wrong party is worse than none),
`prerequisite-docs/09_TEST_PLAN.md` (the suite must be able to run its
own checks).

## Rollback

Remove the `observe_requests` middleware and the `ops` router, and the
metrics endpoint disappears. Restore the single-counter rate limiter by
keying on the address alone.
