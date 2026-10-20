# ADR 0009 — Egress is a policy, not a config value

- **Status:** accepted
- **Date:** 2026-10-20
- **Related:** release gate "SSRF suite against live webhook hosts"

## Context

The product makes one outbound call: the outbox delivery, which posts an
approved supplier message to a webhook. The URL came from
`OUTBOX_WEBHOOK_URL` and was used with no validation of any kind.

A configuration value is not attacker input, so this was not an
exploitable SSRF as it stood. But it had two problems:

1. A configuration mistake — a URL pointing at the cloud metadata
   endpoint, or at an internal admin port — turned the API into a proxy
   with no guard rail. The class of accident is exactly what the release
   gate's "SSRF suite" was supposed to catch, and there was nothing to
   catch it with.
2. It set the precedent. The next outbound call would inherit the same
   absence of a policy.

The release gate also had a box for this that was unticked and
unanswerable: "SSRF suite against live webhook hosts — pending staging".

## Decision

Make the egress policy explicit, in one module, and route every outbound
call through it.

- The scheme must be `http` or `https`. `file://`, `gopher://`, `ftp://`
  and `data:` are refused.
- The host must be on the allowlist when one is configured
  (`OUTBOX_WEBHOOK_ALLOWLIST`). A host matches exactly, or as a subdomain
  of a listed name.
- Redirects are not followed at all (`follow_redirects=False`), so a 302
  cannot walk a request to a host the allowlist would have refused.

Loopback and private addresses are **not** blanket-refused. A staging
webhook host is very often on a private network, and the allowlist is the
right control for that: it turns the set of reachable destinations from
something implied into something declared.

The drill (`scripts/ssrf_drill.py`) starts a real HTTP server on
localhost and proves all of it: the delivery reaches the webhook, a host
outside the allowlist is refused, a non-http scheme is refused, a 302 is
not followed, and a disallowed destination is not reached.

## Consequences

- The outbox delivery refuses a destination the policy does not permit
  and the message stays queued — the approval still authorised it, the
  transport simply did not carry it.
- `OUTBOX_WEBHOOK_ALLOWLIST` is a new environment key, blank by default
  (no allowlist means "any http(s) host", which is the current
  behaviour).
- A future outbound call has one place to go through.
- The release gate box can be answered with a command:
  `python scripts/ssrf_drill.py`.

## Brain refs

`prerequisite-docs/08_SECURITY_AND_COMPLIANCE.md` (egress is a control,
and a control that is only a convention is not a control).

## Rollback

Remove the `check_url` call in `app/actions/service.py::_deliver`. The
allowlist key becomes unused; the drill then fails, which is the point.
