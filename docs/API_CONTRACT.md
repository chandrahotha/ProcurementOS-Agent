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

## Live (all covered by `tests/test_api.py`)

| Method & path | Notes |
|---|---|
| GET `/healthz`, GET `/api/v1/health` | DB probe (503 when down) + redis boolean |
| POST `/missions` · GET `/missions` · GET `/missions/{id}` · PATCH `/missions/{id}` | Dial increase needs Manager; deadline must be an ISO date |
| POST `/missions/{id}/advance` | Validates `machine.check_transition` against live rows; backward moves role-gated; waivers Compliance-gated; 422 carries missing-field list on coverage refusal |
| POST `/missions/{id}/documents` · GET `/missions/{id}/documents` | Quarantine verdicts; full-archive macro scan; 25 MB byte cap during read |
| POST `/missions/{id}/plans` · GET `…/plans/current` · GET `…/plans/{v}/diff` · POST `…/plans/{v}/acknowledge` | Ack needs Manager (roles map is the source); 409 on version race; acknowledge enqueues tasks onto the pos:* queue |
| GET `/missions/{id}/tasks` · POST `…/tasks/{key}/retry` · POST `…/tasks/{key}/review` | Task select pins plan_version (unique index backstops); retry key persisted + replay-safe; blocked tasks refuse review |
| GET `/missions/{id}/evidence` · POST `…/evidence/spans` · PATCH `…/evidence/{spanId}` | Span documents validated (real, in-mission, clean — `manual-entry` sentinel = outage fallback); corrections re-scanned; hostile spans flagged on write |
| POST `/missions/{id}/analyze` · GET `…/results/sourcing` · GET `…/results/cost` · GET `…/results/risk` | Runs `engine/*` (`price_uom` honored per ADR-0005), pins rule_version, persists rows + real evidence refs + SourceLinks; failed runs roll back partial results |
| POST `/missions/{id}/scenarios` · POST `…/scenarios/optimize` | Optimize needs Manager; infeasible → 422 with repair hints, never relaxed; capacity-aware order-independent baseline |
| POST `/missions/{id}/negotiation/drafts` | Ladder rungs span opening→target; above walk-away refused; hostile text refused; never sends |
| GET `/missions/{id}/brief` | Ranked winner + deltas + cited lines; records `brief_generated` once (not per read) |
| POST `/missions/{id}/approvals` · POST `…/approvals/{aid}/decide` | Lane roles enforced (managers out of finance/compliance lanes — dual control is structural); Admin cannot approve; decisions terminal; reject needs reason; 410 on expired |
| POST `/missions/{id}/actions/dry-run` · POST `…/actions/execute` | Verdict from server-computed quorum only; execute needs `Idempotency-Key`; unknown action class never satisfies quorum; no quorum → 403 + block audit; replay returns receipt (mission-scoped) |
| GET `/missions/{id}/runs` · POST `…/runs/{rid}/replay` | Replay needs Manager; run row validated; recomputes from stored inputs, reports match/diverged (nothing compared → never "match"); TCO integrity skips FX-converted rows |
| POST `/missions/{id}/export` | CSV/XLSX/PDF bytes + manifest; every scope id tenant-checked; formula-injection neutralized in cells; cross-tenant smuggling → 403 |
| GET `/missions/{id}/timeline` | Timeline events + audit trail, SQL-filtered `since` cursor, capped |
| GET `/workspaces` | Member workspaces (P02 picker; Admin sees all in tenant) |
| GET `/missions/{id}/scenarios` | Scenario rows (P10 list) |
| GET `/missions/{id}/approvals` | Approval rows for the mission (P13 queue + quorum read) |
| GET `/audit` | Tenant-wide hash-chained events, newest first (G13; full `event_hash` + `prev_hash`; `limit` ≤ 500, ≥ 0) |
| GET `/audit/verify` | Re-walks the tenant's chain end to end; reports intact/broken_at |
| GET `/rules` | Rule versions in this tenant (G16 read model) |
| POST `/missions/{id}/actions/settle` | Records approved actions executed/skipped (04 §1 action→report gate) |
| GET `/suppliers` · GET `/suppliers/{id}` | Tenant directory + profile (site, OTD/PPM KPIs, risk history) joined from certified results |
| GET `/ai-jobs` | Tenant-wide AI run history (G17) |
| GET `/notifications` | Derived feed: pending approvals + gate rejections, newest first (G05) |

`/cases/*` mirrors `/missions/*` with the same handlers.

Auth: prod requires OIDC (`OIDC_ISSUER`/`OIDC_AUDIENCE`) — the app
refuses to boot in production without both; the dev-token fallback is
dev/test only (tokens stored hashed). Per-IP rate limiting on
write methods (429 with the error envelope).
