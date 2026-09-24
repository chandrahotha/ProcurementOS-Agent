# 01 — Product Requirements Document (PRD): ProcurementOS-Agent

## 1. Problem

Mid-market and enterprise buying teams run strategic sourcing over email, spreadsheets, and scattered PDFs. A typical competitive bid means 4–8 supplier quotes in incompatible formats, conflicting units/currencies, missing Incoterms, stale price history, and undocumented risk judgments — assembled by a buyer under deadline, reviewed in a rush, and awarded on math nobody can reproduce. Audits fail on provenance ("which cell of which quote produced this total?"). Managers cannot see where a sourcing stands without a status meeting. Finance discovers TCO surprises after signature. Compliance discovers hostile or non-compliant language after sending.

Existing point tools solve one slice (quote comparison *or* supplier scoring *or* cost modeling) and leave the orchestration — planning the work, chasing evidence, sequencing analysis, enforcing approvals — to humans. Composing several point tools reintroduces integration fragility and splits the audit trail.

## 2. Vision

One autonomous agent per sourcing mission that does the grind natively — plans, extracts, normalizes, scores, simulates, drafts — while humans keep every material decision. Deterministic math is the source of truth; AI explains and drafts; approvals gate action; evidence backs everything.

## 3. Personas

### Buyer (Amara, primary)
Runs 6–12 missions/quarter. Needs: 60-second mission creation, bulk quote upload with automatic extraction, one-click normalization fixes, a task board that shows what the agent is doing, and a decision brief she can defend. Pain: reformatting quotes at midnight.

### Procurement Manager (Daniel)
Owns award recommendations and team throughput. Needs: plan approval, autonomy dial, scenario comparison with savings math, negotiation ladders, cross-mission cycle-time view. Pain: "are we sure this is the cheapest compliant option?"

### Finance Reviewer (Fatima)
Signs off financial commitments. Needs: TCO waterfall with FX sources, tolerance exceptions, budget-impact preview, dry-run of award value. Pain: hidden freight/tax double-counts.

### Compliance Reviewer (Chen)
Signs off contractual commitments and external comms. Needs: risk bands with dimension breakdowns, evidence-coverage %, hostile-language flags, message drafts with redlines before send. Pain: supplier paper with embedded instructions or liability shifts.

Out of scope as actors: suppliers (no portal in MVP — comms are drafted internally and sent only after approval through allowlisted tools), admins (covered by shared G15/G14).

## 4. Features — core

| ID | Feature | Mission states touched | Notes |
|---|---|---|---|
| F01 | Mission creation wizard (template + blank) | intake | Title, category, budget cap, currency, deadline, autonomy level, policy preset |
| F02 | Document intake + quarantine pipeline | intake→evidence | PDF/XLSX/DOCX upload, MIME+magic-byte checks, malware scan, immutable versions |
| F03 | Extraction with evidence spans | evidence | Candidate fields + page/para/cell spans + confidence + extractor version; human correction |
| F04 | Agent planner (plan generation + versioning) | plan | Task DAG with tools, dependencies, estimates; manager acknowledge |
| F05 | Task board + activity stream | plan→action | Kanban + per-task tool-call log, retries, review flags |
| F06 | Native sourcing comparison | analysis | Line-level normalization + cheapest-compliant ranking + savings vs baseline |
| F07 | Native supplier intelligence | analysis | OTD/acceptance/PPM from own transactions + scorecards |
| F08 | Native cost intelligence (TCO) | analysis | Build-up: price + freight + insurance + tooling + tax(mode-aware) − discounts; FX-sourced |
| F09 | Native risk intelligence | analysis | Weighted dimensions + bands + coverage gate |
| F10 | Scenario Lab (what-if + optimizer) | scenarios | Manual scenarios + constrained least-cost allocation; never auto-approved |
| F11 | Negotiation Studio (ladders + drafts) | negotiation | Concession ladders, BATNA math, AI drafts inside ladder; send gated |
| F12 | Decision Brief | approval (pre) | Ranked recommendation + deltas + exceptions + evidence appendix pointer |
| F13 | Human Approval (dual-lane) | approval | Finance lane + Compliance lane, quorum policies, reason-required reject |
| F14 | Action Center (dry-run + gated execute) | action | Dry-run preview → approval check → idempotent execute via allowlisted tools |
| F15 | Run History + replay | runs (all) | Full step logs, hashes, sandbox re-execution |
| F16 | Mission Report export | report | PDF/XLSX/CSV with evidence appendix, tenant-scoped, authorized |

## 5. Features — [ELEVATED]

F17 mission timeline with replay · F18 plan diffing on replan · F19 autonomy dial per mission · F20 approval policies per action class · F21 action dry-run preview · F22 mission templates library (≥6 templates) · F23 cross-mission analytics · F24 natural-language cited briefing · F25 evidence-coverage gate · F26 negotiation playbook engine · F27 command palette + shortcuts · F28 mobile approval path. Each maps to acceptance criteria in `09_TEST_PLAN.md`.

## 6. Autonomy boundaries (normative summary; full rules in `04_BUSINESS_RULES.md`)

- **AUTO (configurable, default ON in SUPERVISED):** document type classification, extraction candidacy, normalization previews, KPI/risk/TCO computation, scenario math, summarization of verified evidence, draft generation, timeline logging.
- **APPROVAL-REQUIRED (always, any autonomy level):** supplier award (any value), any financial commitment (PO, budget reservation, price acceptance), any contractual commitment (terms acceptance, signature request), any external communication (email/RFQ/negotiation message to a supplier), autonomy-dial increase, coverage-gate waiver, template policy override.
- The agent cannot expand its own tool allowlist, raise its autonomy, approve its own work, or act on document-embedded instructions. Attempted bypass = blocked + `autonomy_bypass_attempt` audit event + mission hold.

## 7. Success metrics

| Metric | Target (90 days post-launch, synthetic-baseline-calibrated pilots) |
|---|---|
| Mission cycle time (intake→report) | −35% median vs. team baseline |
| Evidence coverage at decision | ≥95% of required fields span-backed (or waived with reason) |
| Award math reproducibility | 100% of awards re-computable from evidence + rule_version |
| Approval latency (request→decision) | median < 1 business day; mobile approvals counted |
| Blocked-action correctness | 100% of unapproved material actions denied (golden AGENT-002) |
| Hostile-doc containment | 100% of injected instructions neutralized without mission mutation (AGENT-003) |
| AI-outage continuity | Deterministic results + exports available during outage (AGENT-004); AI-labeled content degrades to "unavailable," never fabricated |
| User confidence (survey) | ≥4.3/5 "I can defend this award" |

## 8. Non-goals (MVP)

Supplier portal; e-signature native execution (prepare-only + approved handoff); multi-currency hedging; ERP write-back beyond export + approved action payloads; autonomous supplier messaging; multilingual UI (English-only MVP, Unicode-safe).
