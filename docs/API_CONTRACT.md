# API contract — ProcurementOS-Agent (live inventory)

Mirrors `prerequisite-docs/05_WORKFLOWS_AND_API.md`. Grows as phases land.
Base `/api/v1`, tenant-scoped. Success envelope
`{"data":{},"meta":{"request_id","version":"v1"}}`; errors
`{error:{code,message,details},request_id,meta:{version}}`.
`Idempotency-Key` on all async POSTs (extraction, analysis, optimizer,
replay, export, task retry, approvals, actions).

## Phase 0 (live)

| Method & path | Purpose |
|---|---|
| GET `/healthz` | Process health |
| GET `/api/v1/health` | API health |

## Phase 2+ (planned — see brain §2 table)

missions, documents, plans (+diff/acknowledge), tasks (+retry/review),
evidence, analyze, results/sourcing|cost|risk, scenarios (+optimize),
negotiation/drafts, brief, approvals (+decide), actions/dry-run|execute,
runs (+replay), export, timeline. (`/cases/*` mirrors `/missions/*`.)
