# 00 — Improvement Scope: From Generic Template + Composer to Standalone Autonomous Agent

## 1. What the master specs gave us (and where they fall short)

The master inputs for this product (`PRODUCTS/05_PROCUREMENTOS/00–10,12,13`) plus the GLOBAL manuals establish a solid enterprise floor: mission states (intake→plan→evidence→analysis→scenarios→negotiation→approval→action→report), autonomy boundaries (automate reading/analysis/drafting; never auto-award/commit/message), allowlisted typed tools, evidence-linked AI, tenant isolation, and golden tests AGENT-001…004. We adopt all of it.

Gaps found during review:

1. **Composer assumption.** The master narrative around this product implies it achieves breadth by composing the other four products. That creates hidden coupling (shared schemas, cross-service auth, cascading outages, blurred audit ownership) and makes the product undeployable alone. This brain removes that assumption entirely.
2. **Generic-template depth.** The product files are 8–26 lines each: state names without transitions/guards, "product_result" without formulas, "allowlisted tools" without a registry, 16 screens as name+route only, golden tests as IDs only. Nothing here is buildable without invention.
3. **No mission-state machine semantics.** No entry/exit criteria, no who-may-advance rules, no replan/rollback semantics, no terminal-state policy.
4. **No native analysis math.** No sourcing-normalization formula, no TCO build-up, no supplier KPI definitions at product level, no risk-score model with weights/versions, no scenario optimizer objective/constraints.
5. **No tool registry.** No tool names, schemas, idempotency keys, authorization mapping, or dry-run semantics.
6. **No autonomy model beyond a sentence.** No per-action-class policy, no per-mission dial, no dual-control thresholds.
7. **No injection-isolation design.** "Document text never becomes instructions" is stated but not mechanized (no extraction boundary, no instruction-scan, no quarantine of hostile spans).
8. **No outage-fallback design.** "AI failure must not destroy deterministic results" with no degraded-mode UX or run-state handling.
9. **No screen behavior.** 16 routes with zero layout/component/state specification; shared screens unmapped.
10. **No seed/demo/deploy concreteness.** Counts given (3 buyers, 6 suppliers, 12 items, 24 transactions, 10 edge cases) but no records, no hostile-doc fixture, no demo narrative, no rollback plan.

## 2. The standalone redefinition (binding decision)

**ProcurementOS-Agent is a fully standalone product.** It does not orchestrate, import, or call RFQLens, SupplierRadar, CostPilot, or ContractGuard at runtime or build time. Rationale:

- **Deployability:** one repo, one schema, one deploy. A buyer team can adopt the agent without adopting four other systems.
- **Audit clarity:** every result's lineage stays inside one tenant boundary, one `rule_version`, one evidence store. No cross-product provenance chains to reconcile.
- **Blast-radius control:** an outage or compromise in a sibling cannot halt or taint a mission. AGENT-004 (AI outage fallback) extends naturally to "sibling outage = irrelevant."
- **Determinism ownership:** the deterministic engine is the source of truth, versioned here (`rule_version` per run). Borrowing another product's math would split version authority.
- **Security:** no cross-service tokens, no confused-deputy calls, no shared buckets. The tool registry is the only action surface, and it lives here.

Concretely, this brain specifies four **native deterministic modules** that replace any composer need:

| Native module | Owns | Key outputs |
|---|---|---|
| `sourcing_compare` | Quote normalization, line-level award math, landed-cost ranking | Normalized quote lines, cheapest-compliant per line, savings vs. baseline |
| `supplier_intel` | Native supplier master + KPI computation from this product's transactions | OTD %, acceptance %, PPM, open-risk count, evidence-linked scorecards |
| `cost_intel` | TCO build-up, price-history variance, should-cost deltas | TCO per supplier/scenario, waterfall deltas, tolerance flags |
| `risk_intel` | Configurable weighted risk model + evidence coverage check | Dimension scores, composite band (LOW/MEDIUM/HIGH/CRITICAL), coverage % |

AI never computes these; AI explains and drafts from them.

## 3. Feature elevations [ELEVATED] (12)

1. **Mission timeline with replay.** Every state transition, task run, approval, and action is an append-only timeline event; any Rangeselected point re-renders the mission snapshot (plan version, results hash, evidence set) for audit replay.
2. **Plan diffing on replan.** Replanning produces a versioned `MissionPlan` with a field-level diff (added/removed/retimed tasks, changed tools, changed dependencies) requiring manager re-acknowledgement when material.
3. **Task board with agent activity stream.** P05 pairs a Kanban (queued/running/needs-review/blocked/done) with a live append-only activity feed per task (tool calls, retries, evidence citations added).
4. **Autonomy-level dial per mission.** `ASSISTED` (every tool call needs confirmation) / `SUPERVISED` (auto read/analysis/draft, approval for material) / `GUARDED` (auto within tight value/risk caps, dual approval above). Dial changes are themselves audited approvals.
5. **Approval policies per action class.** Matrix of action class × value/risk band → required approver roles + quorum (e.g., award > €50k needs Manager + Finance; external comms always need Compliance or Manager).
6. **Action dry-run preview.** Every material action renders a deterministic dry-run (exact payload, recipients, value impact, policy result ALLOW/DENY/NEEDS-APPROVAL) before it can be requested or approved.
7. **Run history with full replay (P15).** Each `MissionRun` stores inputs hash, tool versions, rule version, evidence snapshot, and step log; one-click re-execution in sandbox reproduces or diffs results.
8. **Mission templates library.** Templated intake forms + plan skeletons + policy presets for repeat buys (e.g., "MRO spot buy," "Capex competitive bid," "Sole-source renewal") with versioned template IDs.
9. **Cross-mission analytics.** Portfolio view: cycle-time by stage, approval-latency heatmap, savings realized vs. recommended, top exception causes, agent retry rates — computed from own missions only.
10. **Natural-language mission briefing.** "Brief me" generates a cited, evidence-linked status brief (state, blockers, top-3 decisions, next approvals) from the deterministic snapshot; every sentence carries span citations or is labeled analytical.
11. **Evidence-coverage gate.** Analysis, scenarios, and decision brief each compute `coverage %` (required fields backed by spans); below-threshold missions cannot advance state until gaps are resolved or formally waived with reason.
12. **Negotiation playbook engine.** Deterministic concession-ladder and BATNA math per supplier (walk-away, target, opening) derived from scenario deltas; AI drafts messages strictly inside the approved ladder and never sends without approval.

## 4. UI/UX elevations [ELEVATED] (12)

1. **Design tokens + dark mode.** CSS-variable token set (color, type, spacing, radius, elevation) with light/dark/contrast themes; dark mode is first-class on all 16 screens, verified for table density.
2. **Agent-activity visualizations.** Live run pulse, per-task tool-call sparkline, state-progress rail (9 states), and autonomy-dial gauge — ambient, non-blocking, pause-safe.
3. **Drawer evidence pattern.** Any number, claim, or recommendation opens an Evidence Drawer showing the exact document spans (page/paragraph/table cell), extractor version, confidence, and correction affordance — never a bare tooltip.
4. **Keyboard shortcuts + command palette.** `Cmd+K` mission-wide: advance state, request approval, dry-run action, jump screens, brief me. Full shortcut map (`g then m` Mission Control, `a` approvals, `?` overlay).
5. **Mobile approval.** P13 is fully usable at 360px: stacked diff cards, big Approve/Reject with reason field, biometric-gated session, offline queue with conflict warning.
6. **Onboarding checklist + sample mission.** First-run wizard creates a synthetic sample mission end-to-end (intake→report) in under 5 minutes without touching real data.
7. **Empty/partial/denied/stale states per screen.** Every P-screen ships all seven states (loading, empty, partial, success, error, denied, stale/processing) with exact copy and recovery actions — specified in §06.
8. **Density modes.** Comfortable/compact table density toggle persisted per user; compact keeps evidence affordances reachable in one click.
9. **Optimistic-but-honest mutations.** Mutations show pending state with idempotency key; conflicts surface a three-way diff (mine/theirs/base) instead of silent overwrite.
10. **Exception-first layouts.** Every intelligence screen (P07–P09) leads with an exception banner row (count + worst item + jump link) above the data, not below.
11. **Guided correction flows.** Extraction conflicts open inline row editors with source-span context, unit/currency normalization preview, and "apply + re-run analysis" in one gesture.
12. **Accessibility contract.** WCAG 2.2 AA: focus-visible rings, 4.5:1 text contrast in both themes, full keyboard paths for approvals and drawers, live-region announcements for agent progress and gate blocks, reduced-motion mode that freezes ambient visualizations.

## 5. Traceability of elevations

Every [ELEVATED] item above has a home: features → `01_PRD.md` §4–5 and `05_WORKFLOWS_AND_API.md`; UI → `06_UI_UX_SYSTEM.md`; autonomy/policy → `04_BUSINESS_RULES.md`; replay/provenance → `03_DOMAIN_MODEL.md` + `07_AI_ARCHITECTURE.md`; tests → `09_TEST_PLAN.md`; seed/demo → `10_SEED_DEMO_DEPLOY_ROADMAP.md`.
