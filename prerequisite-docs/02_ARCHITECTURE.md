# 02 — Architecture: ProcurementOS-Agent (Standalone)

## 1. Stack (pinned at build)

- **Frontend:** Next.js 14 (App Router) + TypeScript 5 + Tailwind CSS + shadcn/ui + React Hook Form + TanStack Table + Zod. Data fetching via server actions / route handlers calling the FastAPI backend; no direct DB access from the browser.
- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic migrations.
- **Data:** PostgreSQL 16 (system of record), S3-compatible object storage (immutable document versions, export artifacts), Redis (agent-task queue via RQ/Celery-compatible worker + rate limits + idempotency locks), optional DuckDB/Polars in-worker for analytics frames.
- **Agent runtime:** DB-backed mission-state engine (state machine enforced in domain service, not the LLM) + native deterministic analysis package (`engine/`: sourcing_compare, supplier_intel, cost_intel, risk_intel, scenario_opt) + tool registry (`tools/`: typed, allowlisted, permission-checked) + worker pool executing `MissionTask`s.
- **AI:** provider abstraction (OpenAI-compatible + one fallback provider), structured JSON output only, prompt/version registry, retrieval limited to own evidence store. OR-Tools for scenario optimization.
- **Testing/deploy:** pytest, Vitest, Playwright, pip-audit/npm-audit, gitleaks; Vercel for web; controlled API/worker runtime (Docker); managed Postgres; WAF + rate limits; OpenTelemetry traces + structured logs.

```
Browser → Edge/WAF → Next.js → authenticated FastAPI → domain services
   → Postgres / S3 / Redis-queue → worker (mission engine + native analysis + allowlisted tools)
   → AI provider (only for explain/draft/extract-candidate; never for math, never direct DB)
```

## 2. Modules (backend `app/`)

| Module | Responsibility |
|---|---|
| `missions/` | Mission CRUD, state machine, timeline events, autonomy dial, coverage gate |
| `plans/` | Plan generation/validation/versioning/diff, DAG integrity |
| `tasks/` | Task lifecycle, queue dispatch, retries, review flags, activity stream |
| `ingest/` | Upload → quarantine → validation → malware scan → immutable version → extraction jobs |
| `evidence/` | EvidenceSpan store, conflict detection, corrections, coverage computation |
| `engine/sourcing_compare` | Quote normalization + line ranking + savings (Decimal-only) |
| `engine/supplier_intel` | KPI computation (OTD/acceptance/PPM) + scorecards |
| `engine/cost_intel` | TCO build-up + FX handling + variance vs history |
| `engine/risk_intel` | Weighted risk dimensions + bands + provenance |
| `engine/scenario_opt` | Manual scenarios + OR-Tools constrained allocation |
| `negotiation/` | Ladders/BATNA math + draft management (send gated) |
| `approvals/` | Policy evaluation, quorum, lanes, expiry, waivers |
| `actions/` | Dry-run renderer + approval check + idempotent execution via tool registry |
| `tools/` | Tool definitions, JSON-schema I/O, auth mapping, audit wrap (THE ONLY action surface) |
| `ai/` | Provider routing, schema validation, run metadata, fallback handling |
| `reports/` | Export builders (PDF/XLSX/CSV) + evidence appendix |
| `audit/` | Append-only AuditEvent writer, hash chaining |
| `auth/` | OIDC, RBAC, object-level checks, tenant scoping middleware |

Frontend `web/`: `app/agent/...` routes P01–P16, `components/` (shell, tables, drawers, panels per `06_UI_UX_SYSTEM.md`), `lib/api-client.ts` (typed, request_id propagation).

## 3. Repo layout

```
procurementos-agent/
  web/  (Next.js: app/agent/*, components, lib)
  app/  (FastAPI: missions plans tasks ingest evidence engine negotiation approvals actions tools ai reports audit auth)
  worker/ (queue consumers: extract_worker, task_worker, export_worker)
  alembic/ (migrations; mission tables namespaced pos_*)
  engine/tests/ (deterministic golden vectors)
  tests/ (pytest: unit integration e2e security ai-eval)
  web/tests/ (vitest + playwright)
  seed/ (synthetic seed scripts + fixtures incl. hostile docs)
  docs/screenshots/
  docker-compose.yml  Dockerfile.api  Dockerfile.worker  Dockerfile.web
  .env.example  LICENSE  SECURITY.md  CONTRIBUTING.md
```

Own schema prefix `pos_*`; own S3 prefix `pos-tenant-{id}/`; own queue namespace `pos:*`. No shared tables/buckets/queues with any other system.

## 4. Key flows

**Document flow:** upload → quarantine (MIME+extension+magic-byte, size/decompression caps) → malware scan → immutable `DocumentVersion` (SHA-256) → extraction job (candidate fields + spans, instruction-scan) → human correction → coverage update → deterministic analysis → AI explanation (labeled) → approval → export → audit. Macros/scripts never executed; OCR output treated as untrusted data.

**Mission-task flow:** plan task (tool name + typed args + idempotency key) → policy check (autonomy class + dial) → enqueue → worker executes ONLY via `tools.registry.dispatch` → result persisted + timeline event + evidence citations attached → needs-review if low confidence/conflict/material → state gate re-evaluated. Retries with exponential backoff + jitter; poison tasks quarantined after N attempts.

**Material-action flow:** intent → dry-run render → policy evaluation (ALLOW/DENY/NEEDS-APPROVAL + required lanes) → approval request(s) → quorum check → idempotent execute (key = mission+action+version) → receipt + audit. Unapproved execute calls are rejected at the service layer even if the UI is bypassed (AGENT-002).

**AI-outage flow:** provider failure/timeout/schema-fail → run marked `degraded`, deterministic results served unchanged, AI panels show "explanation unavailable — math unaffected," drafts disabled with reason, mission continues to approval/report (AGENT-004).

## 5. Scaling, resilience, observability

Stateless API + horizontally scaled workers; queue depth + task-age alerts; Postgres read replica for analytics; S3 versioning + lifecycle; Redis persistence for idempotency keys (TTL 30d). OpenTelemetry spans per mission/task/tool-call with `request_id`/`mission_id`/`run_id` baggage; dashboards for cycle-time, approval latency, retry rate, coverage distribution. PII minimization: supplier contacts tokenized in logs.
