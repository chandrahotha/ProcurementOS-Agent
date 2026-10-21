# API contract — ProcurementOS-Agent (live inventory)

Mirrors `prerequisite-docs/05_WORKFLOWS_AND_API.md`. Base `/api/v1`,
tenant-scoped. Success envelope
`{"data":{},"meta":{"request_id","version":"v1"}}`; errors
`{error:{code,message,details},request_id,meta:{version}}` — including
401/403/409/410/413/422/429/500 (explicit handlers; FastAPI's default
shape never leaks — malformed bodies carry the same envelope via the
`RequestValidationError` handler). Inbound `X-Request-ID` is truncated
to 64 chars. `Idempotency-Key` honored on task retry (persisted per
task, replays return the original outcome), analysis (failed runs never
replay), export (recorded; deterministic by construction), and execute
(replays return the original receipt).

The inventory below is generated from the OpenAPI schema and is checked
against it, not written from memory:

```powershell
python scripts/api_inventory.py
```

## Auth

| Method & path | Notes |
|---|---|
| POST `/auth/login` | PBKDF2-SHA256 password verification; issues a session token stored **hashed** at rest, expiry-bound and revocable. Identical response for an unknown email and a wrong password, so the endpoint does not enumerate accounts |
| GET `/auth/me` | The resolved principal: user id, email, roles, tenant |
| POST `/auth/logout` | Revokes the presented session; the token stops working immediately |

## Live (all covered by `tests/test_api.py`)

| Method & path | Notes |
|---|---|
| GET `/healthz`, GET `/api/v1/health` | DB probe (503 when down) + redis boolean |
| POST `/missions` · GET `/missions` · GET `/missions/{id}` · PATCH `/missions/{id}` | Dial increase needs Manager; deadline must be an ISO date; the base currency is INR |
| POST `/missions/{id}/advance` | Validates `machine.check_transition` against live rows; backward moves role-gated; waivers Compliance-gated; 422 carries missing-field list on coverage refusal |
| POST `/missions/{id}/documents` · GET `/missions/{id}/documents` | Quarantine verdicts; full-archive macro scan; 25 MB byte cap during read |
| POST `/missions/{id}/plans` · GET `…/plans/current` · GET `…/plans/{v}/diff` · POST `…/plans/{v}/acknowledge` | Ack needs Manager (roles map is the source); 409 on version race; acknowledge enqueues the plan's tasks onto the pos:* queue, **or runs them in the API process when no broker is reachable** — the response says which (`execution`: `queue` \| `inline`) |
| GET `/missions/{id}/tasks` · POST `…/tasks/run` · POST `…/tasks/{key}/retry` · POST `…/tasks/{key}/review` | Task select pins plan_version (unique index backstops); retry key persisted + replay-safe; blocked tasks refuse review; `tasks/run` re-runs the current plan on demand, in dependency order |
| GET `/missions/{id}/evidence` · POST `…/evidence/spans` · PATCH `…/evidence/{spanId}` | Span documents validated (real, in-mission, clean — `manual-entry` sentinel = outage fallback); corrections re-scanned; hostile spans flagged on write; **a correction that disagrees with a pending one is refused with 409 `evidence_conflict`** and the stored value is left alone (the three-way rule: both sides differ from the base *and* from each other) |
| POST `/missions/{id}/analyze` · GET `…/results/sourcing` · GET `…/results/cost` · GET `…/results/risk` | Runs `engine/*` (`price_uom` honored per ADR-0005), pins rule_version, persists rows + real evidence refs + SourceLinks; failed runs roll back partial results |
| POST `/missions/{id}/scenarios` · POST `…/scenarios/optimize` | Optimize needs Manager; infeasible → 422 with repair hints, never relaxed; capacity-aware order-independent baseline |
| POST `/missions/{id}/negotiation/drafts` | Ladder rungs span opening→target; above walk-away refused; hostile text refused; never sends |
| GET `/missions/{id}/brief` | Ranked winner + deltas + cited lines; records `brief_generated` once (not per read); 422 `brief_empty` when there is nothing certified yet, which is a state with a next step and not a failure |
| POST `/missions/{id}/approvals` · POST `…/approvals/{aid}/decide` | Lane roles enforced (managers out of finance/compliance lanes — dual control is structural); Admin cannot approve; decisions terminal; reject needs reason; 410 on expired; the lanes and the threshold are computed from the certified rows and the tenant's rule version, never from the payload |
| GET `/missions/{id}/approvals` | Approval rows for the mission (P13 queue + quorum read); each row carries the **approved payload**, so the action panel can carry the hash-locked payload back |
| POST `/missions/{id}/actions/dry-run` · POST `…/actions/execute` | Verdict from server-computed quorum only; execute needs `Idempotency-Key`; unknown action class never satisfies quorum; no quorum → 403 + block audit; replay returns receipt (mission-scoped) |
| GET `/missions/{id}/runs` · POST `…/runs/{rid}/replay` | Replay needs Manager; run row validated; recomputes from stored inputs, reports match/diverged (nothing compared → never "match"); TCO integrity skips FX-converted rows |
| POST `/missions/{id}/export` | CSV/XLSX/PDF bytes + manifest; every scope id tenant-checked; formula-injection neutralized in cells; cross-tenant smuggling → 403 |
| GET `/missions/{id}/timeline` | Timeline events + audit trail, SQL-filtered `since` cursor, capped |
| GET `/workspaces` | Member workspaces (P02 picker; Admin sees all in tenant) |
| GET `/missions/{id}/scenarios` | Scenario rows (P10 list) |
| GET `/audit` | Tenant-wide hash-chained events, newest first (G13; full `event_hash` + `prev_hash`; `limit` ≤ 500, ≥ 0) |
| GET `/audit/verify` | Re-walks the tenant's chain end to end; reports intact/broken_at |
| GET `/rules` | Rule versions in this tenant (G16 read model): weights, tolerances, FX policy, effective-from, changelog |
| POST `/missions/{id}/actions/settle` | Records approved actions executed/skipped (04 §1 action→report gate) |
| GET `/suppliers` · GET `/suppliers/{id}` | Tenant directory + profile (site, OTD/PPM KPIs, risk history) joined from certified results |
| GET `/ai-jobs` | Tenant-wide AI run history (G17) with the evidence refs of each result |
| GET `/notifications` | Derived feed: pending approvals + gate rejections, newest first (G05) |
| GET `/purchase-orders` · GET `/budget-reservations` · GET `/messages` | The real objects of record the gated tools produced |
| GET `/ops/metrics` · GET `/ops/queue-age` | Prometheus exposition and the queue state; **administrators only** |

`/cases/*` mirrors `/missions/*` with the same handlers.

Auth: an email and a password are exchanged for a session token at
`POST /api/v1/auth/login`; the token is random, stored hashed, expiry-bound
and revocable, and it is the only bearer credential the API accepts. Prod
requires OIDC (`OIDC_ISSUER`/`OIDC_AUDIENCE`) — the app refuses to boot in
production without both, and with an issuer configured an OIDC JWT is the
only thing that authenticates. Write methods are rate limited on
two counters: 120/min per authenticated principal and 600/min per client
address, so one noisy user behind a shared address cannot throttle a
tenant (429 with the error envelope). `X-Forwarded-For` is honoured only
when `TRUSTED_PROXY` is set.
