# API contract — ProcurementOS-Agent (live inventory)

Mirrors `prerequisite-docs/05_WORKFLOWS_AND_API.md`. Base `/api/v1`,
tenant-scoped. Success envelope
`{"data":{},"meta":{"request_id","version":"v1"}}`; errors
`{error:{code,message,details},request_id,meta:{version}}` — including
401/403/422/409 (explicit handlers; FastAPI's default shape never leaks).
`Idempotency-Key` honored on task retry, analysis, export, and execute;
replays return the original run/receipt instead of recomputing.

## Live (all covered by `tests/test_api.py`)

| Method & path | Notes |
|---|---|
| GET `/healthz`, GET `/api/v1/health` | Process / API health |
| POST `/missions` · GET `/missions` · GET `/missions/{id}` · PATCH `/missions/{id}` | Dial increase needs Manager |
| POST `/missions/{id}/advance` | Extra (not in brain table): validates `machine.check_transition` against live rows; 422 carries missing-field list on coverage refusal |
| POST `/missions/{id}/documents` · GET `/missions/{id}/documents` | Quarantine verdicts; macro/mismatch/oversize rejected |
| POST `/missions/{id}/plans` · GET `…/plans/current` · GET `…/plans/{v}/diff` · POST `…/plans/{v}/acknowledge` | Ack needs Manager; seeds 10 tasks |
| GET `/missions/{id}/tasks` · POST `…/tasks/{key}/retry` · POST `…/tasks/{key}/review` | Retry needs `Idempotency-Key` |
| GET `/missions/{id}/evidence` · POST `…/evidence/spans` · PATCH `…/evidence/{spanId}` | Extra `POST spans` covers extraction output + outage manual entry; hostile spans flagged on write |
| POST `/missions/{id}/analyze` · GET `…/results/sourcing` · GET `…/results/cost` · GET `…/results/risk` | Runs `engine/*`, pins rule_version, persists rows + MissionRun |
| POST `/missions/{id}/scenarios` · POST `…/scenarios/optimize` | Optimize needs Manager; infeasible → 422 with repair hints, never relaxed |
| POST `/missions/{id}/negotiation/drafts` | Out-of-ladder and hostile text refused; never sends |
| GET `/missions/{id}/brief` | Ranked winner + deltas + cited lines; records `brief_generated` |
| POST `/missions/{id}/approvals` · POST `…/approvals/{aid}/decide` | Lane roles enforced; Admin cannot approve; reject needs reason; 410 on expired |
| POST `/missions/{id}/actions/dry-run` · POST `…/actions/execute` | Execute needs `Idempotency-Key`; no quorum → 403 + block audit; replay returns receipt |
| GET `/missions/{id}/runs` · POST `…/runs/{rid}/replay` | Replay needs Manager; recomputes from stored inputs, reports match/diverged |
| POST `/missions/{id}/export` | CSV/XLSX/PDF bytes + manifest; cross-tenant smuggling → 403 |
| GET `/missions/{id}/timeline` | Timeline events + audit trail, `since` cursor |
| GET `/workspaces` | Member workspaces (P02 picker; Admin sees all in tenant) |
| GET `/missions/{id}/scenarios` | Scenario rows (P10 list) |
| GET `/missions/{id}/approvals` | Approval rows for the mission (P13 queue + quorum read) |
| GET `/audit` | Tenant-wide hash-chained events, newest first (G13; `limit` ≤ 500) |
| GET `/rules` | Rule versions in this tenant (G16 read model) |
| POST `/missions/{id}/actions/settle` | Records approved actions executed/skipped (04 §1 action→report gate) |

`/cases/*` mirrors `/missions/*` with the same handlers.
