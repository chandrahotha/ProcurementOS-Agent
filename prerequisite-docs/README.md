# ProcurementOS-Agent — Autonomous Procurement Agent (Fully Standalone)

> One mission in, one defensible award out: an autonomous agent that plans sourcing work, gathers evidence, runs native deterministic analysis, and stops at the human gate before anything material happens.

**20-second value:** Create a procurement mission in 60 seconds. The agent plans tasks, extracts evidence from your quotes and contracts, compares suppliers, costs, and risks with auditable math, simulates award scenarios, drafts negotiation moves, and hands you a decision brief — but it cannot award, commit money, or message a supplier without your explicit approval. Every number traces to a document span. Every action traces to an allowlisted tool.

![Mission Control](docs/screenshots/p01-mission-control.png)
*Mission Control: live mission states, autonomy dial, blocked-action banner, evidence coverage.*

- **Live demo:** `https://demo.procurementos-agent.example.com` (synthetic data only, resets nightly)
- **Architecture:** Next.js 14 + TypeScript + Tailwind + shadcn/ui → FastAPI (Python 3.12) → Postgres 16 + S3-compatible storage + Redis queue → own mission-state engine + native deterministic analysis modules + allowlisted tool registry. AI is explanation/drafting only.
- **Workflow:** intake → plan → evidence → analysis → scenarios → negotiation → approval → action → report
- **Security:** tenant isolation, deny-by-default RBAC + object-level auth, upload quarantine, prompt-injection isolation, approval gate for material actions, full audit trail.
- **Synthetic-data statement:** This repository contains ZERO real supplier, price, or contract data. All seed data is clearly marked `SYNTHETIC-*` and exists only for demo and testing.
- **Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, React Hook Form, TanStack Table, Zod · FastAPI, Pydantic v2, SQLAlchemy 2, Alembic · PostgreSQL 16, S3-compatible storage, Redis (queue + rate limits), optional DuckDB/Polars · pytest, Vitest, Playwright · Docker, GitHub Actions, Vercel (web) + controlled API/worker runtime.
- **Quick start:** see `10_SEED_DEMO_DEPLOY_ROADMAP.md` § Deploy (docker compose up → migrate → seed → login as synthetic buyer).
- **Test status:** `pytest` (domain + API + security) · `vitest` (components) · `playwright` (E2E incl. AGENT-001…004 golden tests). CI badge: ![CI](https://github.com/example/procurementos-agent/actions/workflows/ci.yml/badge.svg)
- **Roadmap:** mission templates library → cross-mission analytics → ERP/contract e-sign connectors (behind approval gates) → multilingual briefs. See `10_SEED_DEMO_DEPLOY_ROADMAP.md` § Roadmap.
- **License:** Apache-2.0 (see LICENSE).

## Users

| Role | What they do here |
|---|---|
| Buyer | Creates missions, uploads documents, runs agent tasks, prepares decision briefs |
| Procurement Manager | Owns plan, autonomy dial, scenario selection, award recommendation |
| Finance Reviewer | Reviews cost intelligence, TCO math, tolerance exceptions, approves financial commitments |
| Compliance Reviewer | Reviews risk/evidence coverage, approves contractual commitments and external comms |

**30-second value:** A buyer drowning in 6 quote PDFs and a looming deadline creates a mission, and the agent does the grind — extraction, normalization, supplier/cost/risk math, scenario comparison, negotiation drafts — surfacing only decisions. Finance and Compliance each get their own approval lane. The award is blocked until humans sign. The report exports with evidence appendices auditors accept.

## Brain index

| # | File | Contents |
|---|---|---|
| 0 | `00_IMPROVEMENT_SCOPE.md` | Gap analysis, standalone redefinition, 10+ feature + 10+ UI/UX elevations |
| 1 | `01_PRD.md` | Problem, personas, features (core + [ELEVATED]), autonomy boundaries, metrics |
| 2 | `02_ARCHITECTURE.md` | Stack, mission engine, native analysis modules, tool registry, repo layout, flows |
| 3 | `03_DOMAIN_MODEL.md` | Entities incl. Mission/MissionPlan/MissionTask/MissionRun + Money/Quantity/Evidence/Audit conventions |
| 4 | `04_BUSINESS_RULES.md` | State machine, autonomy classes, tool discipline, injection isolation, prohibitions, golden tests |
| 5 | `05_WORKFLOWS_AND_API.md` | Mission lifecycle workflows + REST endpoints with auth/audit |
| 6 | `06_UI_UX_SYSTEM.md` | THE WOW FILE — tokens, shell, components, full P01–P16 + G01–G20 specs |
| 7 | `07_AI_ARCHITECTURE.md` | In-product orchestrator, validation, injection defense, outage fallback, run metadata |
| 8 | `08_SECURITY_AND_COMPLIANCE.md` | Agent-specific threats, controls, pre-release checklist |
| 9 | `09_TEST_PLAN.md` | Tiers, coverage bar, negatives, golden matrix, acceptance criteria |
| 10 | `10_SEED_DEMO_DEPLOY_ROADMAP.md` | Synthetic seed, demo script, deploy/rollback, GitHub standard, roadmap |

## ISOLATION statement (binding)

- ProcurementOS-Agent owns its database schema, object storage buckets/keys, queue namespaces, configuration, secrets, and deployment. It shares nothing at runtime with any other product or codebase.
- It is explicitly **NOT a composer, orchestrator, importer, or caller** of RFQLens, SupplierRadar, CostPilot, ContractGuard, or any sibling system. There are no network calls, shared libraries, shared schemas, or data imports from sibling products.
- All capabilities that resemble those products — sourcing comparison, supplier intelligence, cost intelligence, risk/contract intelligence — are implemented **natively inside this repository** as deterministic modules (`sourcing_compare`, `supplier_intel`, `cost_intel`, `risk_intel`) operating on this product's own entities and evidence.
- Reference material used during design is design-time only and creates no runtime dependency. A fresh clone deploys and passes all tests with no sibling present.
- Violation test: block all hosts except the app's own API/DB/storage/AI-provider endpoints; the full mission lifecycle including golden tests AGENT-001…004 must still pass.
