# Backend Findings (B1–B57) — app/, worker/

Status: `[ ]` open · `[x]` fixed · `[~]` deferred with ADR.

## Critical bugs

- [x] **B1** `enqueue_task()` never called — worker pipeline dead from the product's view. `app/api/plans_tasks.py:153-202` + `worker/queue.py:28-42`. Acknowledge only flips plan status; tasks stay `queued` forever. → Call `enqueue_task`/`apply_task` inside `acknowledge_plan` after commit.
- [x] **B2** `(mission_id, key)` select raises `MultipleResultsFound` with 2+ plan versions. `app/api/plans_tasks.py:245-253`, `worker/queue.py:142-147`; `generate_plan` (plans_tasks.py:84-98) reuses keys per version. → Unique constraint on `(mission_id, plan_version, key)`; pin current plan version.
- [x] **B3** Failed run commits partial `SourcingResult`/`CostResult`/`RiskResult` rows. `app/api/analysis.py:190-193`. → `await session.rollback()` instead of committing failure state.
- [x] **B4** Evidence refs dropped at persistence; `SourceLink.result_id` is a synthetic string matching no real row. `app/api/analysis.py:130-139`. → Persist `n.evidence_refs`; link to the real result id.
- [x] **B5** Replay reports `"match"` when every event was skipped (`diffs` empty, `all([]) is True`). `app/api/runs_export.py:92`. → Require non-empty diffs.
- [x] **B7** `dry_run` misses `POLICY_OVERRIDE` as material → `"ALLOW / non-material"`. `app/actions/service.py:27`. → Use `policy.MATERIAL_CLASSES`.
- [x] **B8** `quorum_met` returns True for unknown action class (empty lanes) → execute without any approval. `app/approvals/service.py:243-247`, `app/actions/service.py:77-108`. → Empty lane set = refuse.
- [x] **B10** `correct_span` doesn't re-run `scan()` — hostile corrected text evades quarantine. `app/api/evidence.py:167`. → Scan on correction, set `instruction_flag`.
- [x] **B11** Backward transitions (`analysis→evidence`, `approval→negotiation`) have no gate/role checks — Buyer can walk approval→negotiation. `app/missions/machine.py:74-75`. → Gate with forward-edge role checks.
- [x] **B12** `not_found` collapses any non-403/404 exception (DB failure, IntegrityError) into 404. `app/api/missions.py:174-177` + every router; `app/api/common.py:112-119`. → Catch only HTTPException; let others hit the 500 handler.

## Security

- [x] **B20** Manager self-approves both lanes (dual-control broken): `LANE_ROLES["finance"]` includes MANAGER + no `requested_by != approver` check. `app/auth/roles.py:34-38`, `app/approvals/service.py:168-207`. → Remove MANAGER from finance lane and/or enforce requester≠approver.
- [x] **B21** Dev-token fallback silent in prod when `OIDC_ISSUER` unset (default empty). `app/auth/deps.py:33-46`, `app/core/config.py:15`. → Fail hard at startup when `app_env=production` without issuer/audience.
- [x] **B22** Dev tokens guessable (`dev-{email}`); `api_token` stored/compared in plaintext. `seed/seed_pos.py:117`, `app/auth/deps.py:39`. → Hash tokens; timing-safe compare.
- [x] **B23** Dev roles from email prefix — any "admin*" email gets full ADMIN. `app/auth/deps.py:49-59`. → Derive from stored membership.
- [x] **B24** Sync `httpx.get` in async path (JWKS) — event-loop starvation DoS, no negative cache. `app/auth/oidc.py:30-50`. → AsyncClient, negative caching, URI allowlist.
- [x] **B25** OIDC: no clock leeway; empty `oidc_audience` silently narrows validation. `app/auth/oidc.py:53-82`. → `leeway=30` + startup validation.
- [x] **B26** Macro scan first 4096 bytes only; `.xlsx` never checked (vbaProject.bin). `app/ingest/pipeline.py:41`. → Full archive scan for OOXML formats.
- [x] **B27** Upload slurps whole file into memory before the 25MB check. `app/api/missions.py:392`, `app/ingest/pipeline.py:36`. → Stream-read with byte cap.
- [x] **B28** `s3_key` embeds raw client filename — `../../x.pdf` escapes tenant prefix. `app/ingest/pipeline.py:53`. → Sanitize path separators.
- [x] **B29** `record_spans` never validates document (tenant/mission/clean status) — coverage gate gameable. `app/api/evidence.py:92-105`. → Verify document row per span.
- [x] **B30** No rate limiting anywhere (auth/analyze/upload unthrottled). Global. → Per-IP/principal limits on auth + write endpoints.

## Robustness / correctness

- [x] **B15** Inbound `X-Request-ID` unbounded → `AuditEvent.request_id` String(64) INSERT DataError → 500. `app/core/request_id.py:13`, `app/audit/writer.py:66,180`. → Validate/truncate to sane length.
- [x] **B16** Risk dims unvalidated (composite ≥101 → raw 500 via StopIteration, caught only ValueError); analyze payload dict indexing `KeyError` → 500. `app/api/analysis.py:43-49,70-79,104-111,190`. → Pydantic validation for payload; validate dims 0–100.
- [x] **B17** `lanes_for` value_minor coercion: non-numeric string → ValueError → 500 on decide/dry-run/execute. `app/approvals/service.py:121`, `app/api/approvals_actions.py:124-133,169-179`. → Defensive coercion.
- [x] **B18** Plan version concurrency: `max(...)+1` without locking → raw 500; concurrent same-key `analyze` → duplicate runs. `app/api/missions.py:64-65`, `plans_tasks.py:65`, `analysis.py:74-77`. → Catch integrity → 409 envelope.
- [x] **B19** `must_member` 403 reveals mission exists (contradicts "Safe 404" comment). `app/api/common.py:27-31`. → 404 for non-members or document.
- [x] **B31** No `RequestValidationError` handler: malformed body returns FastAPI default shape without envelope/request_id (contradicts envelope.py:5). `app/main.py:56-104`. → Register handler emitting `fail(...)`.
- [x] **B32** Audit chain head read without lock/tiebreaker — concurrent writes fork the chain; same-`created_at` ambiguous. `app/audit/writer.py:43-49`. → Advisory lock + order by `(created_at, id)`.
- [x] **B33** Export `assert_scope` never validates other mission_ids belong to tenant; manifest can list foreign ids. `app/reports/exporter.py:18-24`, `app/api/runs_export.py:127-132`. → Tenant-check every scope id.
- [x] **B34** `/audit` returns truncated `event_hash[:16]`, never `prev_hash`, no chain-verification path. `app/api/misc.py:137`. → Full hashes + chain-verify endpoint.
- [x] **B35** `/healthz` + `/api/v1/health` never touch DB/Redis — dead DB reports healthy. `app/main.py:107-119`. → `SELECT 1` + Redis ping, degraded on failure.
- [x] **B36** Negative `?limit=-5` → `LIMIT -5` → 500. `app/api/misc.py:118,124`. → `max(0, min(limit, 500))`.
- [x] **B37** `rows_for` listings unbounded (plans, tasks, evidence, timeline, runs, results). `app/api/common.py:42-45`. → limit/cursor params.
- [x] **B38** `list_missions` N+1 `is_member` per mission. `app/api/missions.py:158-163`. → Load member workspaces once.
- [x] **B39** `timeline` loads all events + fragile `since` string compare. `app/api/plans_tasks.py:365-384`. → SQL filter `created_at >= :since` + cap.
- [x] **B40** `_receipt` scans every receipt event per execute — O(n) growth. `app/actions/service.py:47-57`. → Indexed idempotency column or kind+key query.
- [x] **B41** `_membership_roles` loads all workspaces per request. `app/auth/deps.py:62-70`. → Cache per request.
- [x] **B42** `retry_task` requires Idempotency-Key but never stores/checks it; no attempts cap at API level. `app/api/plans_tasks.py:271-272`. → Persist key, return original outcome on replay.
- [x] **B43** `review_task` accept can set `blocked` → `done`, bypassing quarantine. `app/api/plans_tasks.py:305`. → Refuse review of blocked tasks.
- [x] **B44** `Transaction.ordered_at`, `Approval.expires_at`, `Mission.deadline` are `String(64)` - string comparisons; unparseable expiry silently treated expired. `app/models/foundation.py:134,173`, `app/models/mission.py:34`, `app/approvals/service.py:41-48`. → `DateTime(timezone=True)`. **Closed 2026-10-20** (ADR 0006): the three columns are real timestamps; migration `pos_005` converts them with a deliberate per-column policy for unparseable values; `tests/test_migrations.py` pins the column types and the round trip.
- [x] **B45** Mission gates dead in API: `blocking_conflicts` hardcoded 0 (conflicts module never wired), `ladders_in_policy` derived from wrong event, `idempotency_ok`/`audit_complete` hardcoded True. `app/api/missions.py:287,296,300-302`. → Compute from real state. **Closed 2026-10-20** (ADR 0007): `blocking_conflicts` counts spans with an unresolved correction conflict (the three-way diff is now wired through `base_value` + `conflict_state`, migration `pos_006`); `audit_complete` re-walks the tenant's audit chain through the shared `app/audit/writer.py::verify_chain`; `tests/test_gates_and_tools.py` pins that a conflict blocks the analysis gate and that clearing it unblocks.
- [x] **B46** `AdvanceBody.waiver=True` lets any writer bypass intake requirement; not role-gated. `app/api/missions.py:66-69,283`. → Require Compliance when waiver set.
- [x] **B47** `acknowledge_plan` allows ADMIN but roles map says `[MANAGER]` only. `app/api/plans_tasks.py:162` vs `app/auth/roles.py:18`. → Consistent `require_roles(R.MANAGER)`.
- [x] **B52** `replay_run` accepts any unvalidated run_id; `int(inputs["demand"])` KeyError → 500. `app/api/runs_export.py:26-45,56`. → Validate run row + guard parsing.
- [x] **B53** `TestClient(app, raise_server_exceptions=False)` swallows server exceptions - "fully tested" suite masks raw 500s. `tests/test_api.py:58`. → `raise_server_exceptions=True` + crashing-route tests. **Closed 2026-10-20**: the shared harness in `tests/harness.py` uses `raise_server_exceptions=True`, so a server exception fails a test instead of being flattened into a response.
- [x] **B54** `get_session_factory(url)` ignores `url` arg once cached. `app/db.py:28-34`. → Key cache by URL; dispose test engines.

## Contract gaps / dead code

- [x] **B48** Suppliers directory, notifications, AI-runs list, global search: no backend routes at all despite `Supplier`/`AIJob`/`AIResult` models existing (`app/models/foundation.py:50,138,153`); README claims "Every screen is wired to the API". → Add read endpoints + wire screens.
- [x] **B49** `AIJob`/`AIResult` never written; `run_with_fallback`/`scan_output` referenced only from tests - claimed AI panel/degraded-mode marking not in any request path. `app/ai/provider.py`, `app/ai/output_scan.py`. → Wire through the AI path + persist rows. **Closed 2026-10-20**: the brief endpoint calls the provider and persists `AIJob` + `AIResult`, and the AI-runs panel reads them. The rows were being written *without* `tenant_id`, so the path had always failed with a NOT NULL violation — `tests/test_ai_path.py` found it. The suite now covers the success path, the degraded path, the uncited-claim quarantine and the panel.
- [x] **B50** S3 upload never implemented (boto3 declared, never imported); no document-download endpoint; `sha256`/`s3_key` reference content that doesn't exist. `app/ingest/pipeline.py:46-55`. → Implement put + download, or rename field to make mock explicit.
- [x] **B51** Export ignores Idempotency-Key entirely (contract claims honored). `app/api/runs_export.py:109-131`. → Honor the key.
- [x] **B55** `app/engine/` empty package shadowing real top-level `engine` package. → Delete or make it the engine package.
- [x] **B56** `duckdb`, `polars`, `structlog`, `tenacity` declared but never imported; stale `jose.*` mypy override. `pyproject.toml:29-32,72-74`. → Prune.
- [x] **B57** `worker/extract_worker.py`, `worker/export_worker.py` are docstring stubs; compose never runs them. → Implement or delete.

## Intentional / by design (not counted as bugs)

- `/cases/*` router mirroring (`app/main.py:53`), `Test`-scheme strictness, `json.dumps(default=str)` canon, greedy allocator default (ADR 0003), PyJWT choice (ADR 0004).

## Completion pass (2026-10-20) — C1–C6

Found while closing the deferred items above. These were not in the
2026-09-25 audit; they are the defects that only surface once the
deferred work is done and the suite is asked to prove things it had never
proved.

- [x] **C1** The AI result row was written without `tenant_id`, so the
  whole AI path failed with a NOT NULL violation on every call. The
  provider was never reached in production because `AI_PRIMARY_BASE_URL`
  is empty by default, and no test configured one. `app/api/scenarios.py`
  → the row carries the tenant, and `tests/test_ai_path.py` drives a
  local provider through the brief endpoint and asserts the rows land.
- [x] **C2** An uncited AI claim was rendered as the brief's evidence
  note. The output scan accepts an "analytical" label with no authority,
  which is correct — but the text was then presented as if it were
  certified. `app/api/scenarios.py` → only an evidence-linked claim
  replaces the deterministic note; an uncited one is surfaced separately
  with its citation state visible, and the P12 screen shows it with a
  warning badge.
- [x] **C3** The AI circuit breaker is a module-level singleton (the
  provider is shared, so an outage should silence every caller), which
  made the suite order-dependent: the AGENT-004 outage test tripped it
  and every later test silently fell back. `app/ai/provider.py` →
  `reset_circuit_breaker()`, called around every test.
- [x] **C4** The rate limiter counted by client address alone. Behind a
  reverse proxy every request arrives with the proxy's address, so one
  noisy user throttled the whole tenant; the same shared counter also
  made the split suite answer itself with 429s.
  `app/core/ratelimit.py` → two counters, per authenticated principal
  (120/min) and per address (600/min), with `X-Forwarded-For` honoured
  only behind a trusted proxy. ADR 0010.
- [x] **C5** The outbox delivery used the configured webhook URL with no
  validation, and followed redirects. `app/core/egress.py` → scheme
  allowlist, host allowlist, no redirect following, plus
  `scripts/ssrf_drill.py` as the drill. ADR 0009.
- [x] **C6** There was no observability at all, while the release gate
  claimed "OpenTelemetry wiring exists". `app/core/observe.py` →
  request metrics, counters, queue depth and task age, served as
  Prometheus text from `/api/v1/ops/metrics`. ADR 0010.

## Completion pass, second wave (2026-10-20) - C15-C19

- [x] **C15** The plan's task rows carried `{"depends_on": [...]}` as the
  tool's arguments, so every task with a required argument blocked
  itself. `app/plans/service.py` -> `CANONICAL_ARGS` gives each tool its
  canonical call shape, and the task row stores it.
- [x] **C16** With no broker reachable, an acknowledged plan left all
  ten tasks queued for ever and the mission never moved.
  `worker/queue.py` -> `execute_plan_tasks` runs the plan in the API
  process, in dependency order, with the same `apply_task` and the same
  audit events. The acknowledge response says which transport ran it.
- [x] **C17** The reporting currency was EUR with European supplier
  records. ADR 0011 -> the base currency is INR, the dual-control
  threshold is INR 5,00,000, the imported line keeps a USD invoice so
  the FX path is exercised, and the reference rate is attributed to the
  RBI. The engine was already currency-agnostic; the golden vectors
  were re-derived, not re-scaled, with the derivation in the comments.
- [x] **C18** The synthetic suppliers carried the conventional placeholder
  trade name. ADR 0011 -> opaque identifiers (`SYN-SUP-01` .. `SYN-SUP-06`)
  with a sector and location descriptor. The migration is scripted
  (`scripts/rename_synthetic_identifiers.py`) and idempotent.
- [x] **C19** The Action Center carried a hard-coded placeholder payload
  that could never match an approved hash, so the Execute button was
  permanently disabled. The approved payload now travels from the
  approval row to the action panel.
