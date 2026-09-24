# 05 — Workflows & API: ProcurementOS-Agent

Auth: OIDC Bearer JWT; tenant + workspace membership enforced server-side on every route; RBAC roles Buyer/ProcurementManager/FinanceReviewer/ComplianceReviewer/Admin. All responses include `request_id`; material mutations emit AuditEvents. Error shape: `{error:{code,message,details},request_id}`. Pagination: cursor-based. Idempotency: `Idempotency-Key` header on POST action/approval/task-retry routes.

## 1. Mission lifecycle workflows

**W1 Create→Plan:** POST mission (F01) → system seeds intake checklist → agent planner proposes plan DAG → Manager acknowledges (or Buyer for pre-approved templates) → tasks enqueued. States: intake→plan.
**W2 Evidence build:** upload docs (quarantine→clean) → extract candidates + spans → instruction-scan → buyer corrects conflicts (inline row editor, normalization preview) → coverage gate evaluated → advance. States: plan→evidence.
**W3 Native analysis:** run sourcing_compare → supplier_intel → cost_intel → risk_intel (each a MissionRun with pinned rule_version) → exception banners → buyer resolves gaps. State: analysis.
**W4 Scenarios:** build manual scenarios (split/dual-source/sole-source) + optimizer run (OR-Tools, objective + constraints logged) → mark candidate → savings vs baseline computed. States: analysis→scenarios.
**W5 Negotiation:** playbook ladders + BATNA per supplier → AI drafts inside ladder → internal redline → NO send. States: scenarios→negotiation.
**W6 Decision→Approval:** Decision Brief generated (ranked rec + deltas + exceptions + evidence refs) → approval requests per policy matrix (Finance lane + Compliance lane as required) → quorum → payload hash locked. States: negotiation→approval.
**W7 Action:** dry-run preview → approval-hash re-verified → idempotent execute via allowlisted tools (award record, PO/budget intents, approved message sends) → receipts. State: approval→action.
**W8 Report:** export PDF/XLSX/CSV with evidence appendix → audit completeness check → mission locked. State: action→report.

## 2. REST endpoints (base `/api/v1`, all tenant-scoped)

| Method & path | Roles | Purpose | Audit |
|---|---|---|---|
| POST `/missions` | Buyer+ | Create mission (template_id optional) | mission_created |
| GET `/missions` | All | List (filter state/autonomy/search, cursor) | — |
| GET `/missions/{id}` | Member | Detail + state + coverage + dial | — |
| PATCH `/missions/{id}` | Buyer+ | Edit intake fields / dial (increase needs approval flow) | mission_updated / dial_changed |
| POST `/missions/{id}/documents` (multipart) | Buyer+ | Upload → quarantine receipt | document_uploaded |
| GET `/missions/{id}/documents` | Member | List with scan/extraction status | — |
| POST `/missions/{id}/plans` | Buyer+ | Generate plan (planner params) | plan_proposed |
| GET `/missions/{id}/plans/current` | Member | Current plan + DAG | — |
| GET `/missions/{id}/plans/{v}/diff` | Member | Plan diff vs v-1 [ELEVATED] | — |
| POST `/missions/{id}/plans/{v}/acknowledge` | Manager | Acknowledge plan | plan_acknowledged |
| GET `/missions/{id}/tasks` | Member | Task board (filter status) | — |
| POST `/missions/{id}/tasks/{key}/retry` | Buyer+ | Retry (idempotent) | task_retried |
| POST `/missions/{id}/tasks/{key}/review` | Buyer+ | Accept/flag review | task_reviewed |
| GET `/missions/{id}/evidence` | Member | Spans (filter doc/conflict/flagged) | — |
| PATCH `/missions/{id}/evidence/{spanId}` | Buyer+ | Correct value (before/after) | evidence_corrected |
| POST `/missions/{id}/analyze` | Buyer+ | Run native analysis suite (module selector) | analysis_run |
| GET `/missions/{id}/results/sourcing` | Member | Rankings + line detail | — |
| GET `/missions/{id}/results/cost` | Member | TCO waterfalls + FX sources | — |
| GET `/missions/{id}/results/risk` | Member | Bands + dimensions | — |
| POST `/missions/{id}/scenarios` | Buyer+ | Create manual scenario | scenario_created |
| POST `/missions/{id}/scenarios/optimize` | Manager | Optimizer run (objective+constraints) | scenario_optimized |
| POST `/missions/{id}/negotiation/drafts` | Buyer+ | AI draft inside ladder | draft_created |
| GET `/missions/{id}/brief` | Member | Decision Brief (+ cited NL brief [ELEVATED]) | brief_generated |
| POST `/missions/{id}/approvals` | Buyer+ | Request approval (action_class + payload) | approval_requested |
| POST `/missions/{id}/approvals/{aid}/decide` | Lane role | Approve/reject with reason | approval_decided |
| POST `/missions/{id}/actions/dry-run` | Buyer+ | Dry-run preview (ALLOW/DENY/NEEDS-APPROVAL) | action_dryrun |
| POST `/missions/{id}/actions/execute` | Buyer+ | Gated execute (approval IDs required) | action_executed / award_blocked_no_approval |
| GET `/missions/{id}/runs` | Member | Run history | — |
| POST `/missions/{id}/runs/{rid}/replay` | Manager | Sandbox replay + diff | run_replayed |
| POST `/missions/{id}/export` | Buyer+ | Export report (format) | report_exported |
| GET `/missions/{id}/timeline` | Member | Timeline events (replay cursor) | — |

Cases alias: `/cases/*` mirrors `/missions/*` for template compatibility (same handlers). Auth failures → 401/403 with safe messages; validation → 422 typed errors; conflicts → 409 with diff payload.

## 3. Event/audit hooks

Domain events (outbox → AuditEvent + optional webhook): `mission.state_changed, plan.acknowledged, task.review_needed, evidence.conflict, analysis.completed, approval.quorum_met, action.blocked, report.exported`. Webhooks tenant-signed, replay-safe, never containing document bytes.

### CROSS-CHECK ADD-ON (date 2026-09-24): response envelope, async job lifecycle, and full event catalog

- **Response envelope (binding):** success responses use `{"data": {}, "meta": {"request_id": "...", "version": "v1"}}`. Errors keep the file-header shape `{error:{code,message,details},request_id}` and additionally carry `meta.version`. `request_id` is present on every response including 401/403/422/409; `version` is the API major version pinned at build, bumped only on breaking change.
- **Async job lifecycle (binding for extraction, analysis, export jobs):** `Queued → Validating → Processing → NeedsReview → Complete / Failed`. `Validating` covers quarantine/scan plus request/schema checks; `NeedsReview` covers the human-correction and coverage-gate holds (evidence conflicts, low confidence, hostile flags); `Failed` covers poison/quarantine-terminal outcomes with reason codes. This maps onto the existing task states (`queued/running/needs_review/blocked/done/failed`) and run states (`ok/degraded/failed`): `Validating` ≈ queued + scan verdicts, `Processing` ≈ running, `NeedsReview` ≈ needs_review/blocked, `Complete` ≈ done/ok, `Failed` ≈ failed. Clients poll the run/task resource; every transition emits a timeline event.
- **Full event catalog (extends §3 list above):** `document.uploaded, document.extracted, analysis.started, analysis.completed, risk.updated, scenario.created, approval.requested, approval.completed, approval.quorum_met, action.blocked, export.created, report.exported, security.alert`. Semantics: `analysis.started/completed` bracket each native-engine run; `risk.updated` fires when risk bands recompute after corrections or rule_version change; `scenario.created` fires on manual and optimizer runs (optimizer result included); `approval.requested/completed` bracket each lane decision with `approval.quorum_met` retained as the quorum milestone; `export.created` fires on artifact build with `report.exported` retained as the mission-close milestone; `security.alert` fires on quarantine rejections, hostile-span flags, unknown-tool blocks, and award-block denials.
- **Event/webhook payload rules:** IDs, hashes, state names, and reason codes only — never document bytes, never spans text, never secrets. Webhooks are tenant-signed (HMAC, key in secret manager), carry a replay window (timestamp + nonce, 15-minute tolerance), are replay-safe (idempotency key per event), and deliver only to tenant-allowlisted callback hosts (same SSRF posture as `08_SECURITY_AND_COMPLIANCE.md` T07).
- **Idempotency scope (extends header rule):** ALL async jobs — extraction, analysis suite, optimizer, replay, export — accept `Idempotency-Key`; replays with the same key return the original receipt/manifest instead of recomputing or duplicating side effects. Deterministic math remains the source of truth; retries never alter certified results.
