# 06 — UI/UX System: ProcurementOS-Agent (THE WOW FILE)

## 1. Design language

**Exception-first, evidence-led, calm-density enterprise.** Neutral slate surfaces, one accent (indigo) for agent activity, green/amber/red reserved strictly for compliance/finance meaning (never decoration). Tables are the primary canvas; every claim is one click from its source span. Motion is ambient and honest: the agent looks alive (pulse, stream) but never distracts from numbers; `prefers-reduced-motion` freezes all ambient animation.

## 2. Tokens (CSS variables, light + dark)

```css
/* color */
--bg: #F8FAFC / dark #0B1220; --surface: #FFFFFF / #111A2E; --surface-2:#F1F5F9/#182642;
--border: #E2E8F0 / #243354; --text: #0F172A / #E6EDF7; --text-2:#475569/#9AA9C4;
--accent:#4F46E5; --accent-ink:#FFFFFF; --ok:#15803D; --warn:#B45309; --danger:#B91C1C;
--agent:#6366F1 (activity only); --evidence:#0EA5E9 (span links);
/* type */ --font-sans: Inter, system-ui; --font-mono: "IBM Plex Mono", monospace (numbers/hashes);
--fs-12/13/14/16/20/24/32 scale; tabular-nums everywhere in tables;
/* space */ 4/8/12/16/24/32/48; /* radius */ 6/10/16; /* elevation */ 3 shadow levels;
```
Density: `.density-comfortable` (row 48px) / `.density-compact` (row 32px), persisted per user. Focus ring: 2px accent offset 2px, always visible. Contrast ≥4.5:1 both themes.

## 3. App shell

Top bar: workspace selector · global search (`/` or Cmd+K) · autonomy-dial chip (mission context) · notifications bell with approval-priority inbox · profile. Left nav: Mission Control · Templates · Analytics · Documents · Suppliers · Reports · Audit · Settings. Mission context header (inside a mission): 9-state progress rail (intake→…→report, current pulsing, blocked red, done checked) + coverage ring % + dial badge + "Brief me" button + command palette hint. Right-side global Evidence Drawer host; bottom-left agent-activity toast stack (pausable).

## 4. Component library (all shadcn-based, themed)

AppShell, PageHeader, Breadcrumbs, MetricCard, DataTable (sorting/filtering/column pinning/row expansion/density-aware), FilterBar, StatusBadge (9 mission states + 6 task states + 4 approval states), EvidenceDrawer (span viewer + correction form + confidence + extractor version), ConfidenceBadge, ExceptionBanner (count + worst + jump), RuleExplanation (rule_version + weights popover), AIAssistantPanel (labeled AI output + citations + "unavailable" degraded card), ApprovalPanel (lanes, quorum progress, reason box, expiry countdown), Timeline (append-only, replay scrubber), UploadZone (quarantine states), FileStatus, EmptyState, ErrorState, ConfirmDialog (typed confirm for material acts), DiffViewer (plan/scenario/payload diffs), ExportButton (format + scope note), ScenarioCard, RiskHeatmap, CostWaterfall, ScoreBreakdown, ActivityLog (live stream, pause, filter by tool), AutonomyDial, DryRunCard (ALLOW/DENY/NEEDS-APPROVAL + payload hash), CoverageRing, NegotiationLadder, BriefCard.

## 5. Per-screen UX — P01–P16

**P01 Mission Control `/agent`** — Purpose: portfolio of missions. Layout: KPI row (active missions, awaiting-my-approval, blocked, median coverage) + mission DataTable (title, state badge, coverage ring, dial, deadline countdown, blockers) + right Timeline preview. Interactions: Cmd+K create/jump; row → mission; exception banner "3 missions need review." States: empty (onboarding checklist + "create sample mission"); stale (worker lag note); denied (non-member hidden).

**P02 Create Mission `/agent/new`** — Purpose: 60-second creation. Layout: 3-step wizard (Basics → Scope & Policy → Review): template picker cards (6 templates with policy presets) / blank; fields title/category/currency/budget/deadline/dial; Review shows policy summary + dry-run of first plan. Interactions: template select prefills; validation inline; submit → P03. Empty: n/a; error: field-level + idempotency-safe resubmit.

**P03 Intake `/agent/:id/intake`** — Purpose: define + feed the mission. Layout: intake form (left) + UploadZone + document queue with FileStatus chips (quarantined/scanning/clean/rejected) + required-docs checklist. Interactions: drag-drop bulk upload; rejected file → reason + replace; "generate plan" enabled when checklist complete. Partial: some docs still scanning (progress + proceed-blocked note).

**P04 Agent Plan `/agent/:id/plan`** — Purpose: review/acknowledge the DAG. Layout: plan version tabs + DAG list (task, tool chip, autonomy class, estimate, dependencies) + DiffViewer on replan [ELEVATED] + Acknowledge bar (Manager). Interactions: expand task → args schema preview; replan → diff must be acknowledged if material; ASSISTED mode shows per-task confirm boxes.

**P05 Task Board `/agent/:id/tasks`** — Purpose: live execution. Layout: Kanban (Queued/Running/Needs-review/Blocked/Done) + right ActivityLog stream (tool calls, retries, citations, pause/filter). Interactions: drag = re-prioritize (re-plans dependents, audited); click card → detail + evidence refs + Retry/Accept/Flag; blocked card shows reason + unblock path. Processing state is the default-alive view; stale worker shows banner.

**P06 Evidence Center `/agent/:id/evidence`** — Purpose: provenance truth. Layout: ExceptionBanner (conflicts, hostile flags, low-confidence) + spans DataTable (doc, field, value, page/cell, confidence, extractor v) + quarantine shelf for `instruction_flag` spans with warning. Interactions: click value → document snippet highlight; correct inline (before/after + reason) → coverage recompute + "re-run analysis" nudge. Empty: "no spans yet — upload or run extraction."

**P07 Supplier Intelligence `/agent/:id/suppliers`** — Purpose: native scorecards. Layout: exception banner (worst PPM/OTD) + supplier cards/table: OTD %, acceptance %, PPM (numerator/denominator/period/sources exposed), open risks, evidence links. Interactions: expand → transaction ledger + dimension trend; compare toggle (2–3 suppliers side-by-side). Partial: suppliers with <3 transactions labeled "thin data."

**P08 Cost Intelligence `/agent/:id/cost`** — Purpose: TCO truth. Layout: TCO ranking table + CostWaterfall per supplier (price→freight→insurance→tooling→tax→discounts) + FX source chips (pair/rate/source/time) + history variance flags. Interactions: waterfall segment click → span evidence; toggle tax-mode view; tolerance slider (from rule_version) with re-flag. Denied: Finance-only build-up config hidden from Buyers (view allowed).

**P09 Risk Intelligence `/agent/:id/risk`** — Purpose: risk bands you can defend. Layout: RiskHeatmap (suppliers × dimensions) + band badges + RuleExplanation (weights version, thresholds) + coverage note. Interactions: dimension cell → contributing spans; what-if weight slider (sandbox, labeled analytical, never overwrites certified score); waive (Compliance, reason + expiry).

**P10 Scenario Lab `/agent/:id/scenarios`** — Purpose: what-if + optimize. Layout: ScenarioCards (split/dual/sole + custom) with allocation sliders + objective readout (total landed cost, savings vs baseline) + Optimizer panel (objective, constraints, OR-Tools version, run log) + DiffViewer between scenarios. Interactions: duplicate + tweak; "mark candidate" (Manager); infeasible constraints → plain-language repair hints. Never shows an Approve button here (by design).

**P11 Negotiation Studio `/agent/:id/negotiation`** — Purpose: ladders + drafts, zero sends. Layout: per-supplier NegotiationLadder (opening/target/walk-away from scenario deltas + BATNA card) + draft editor (AI draft inside ladder bounds, bound-violation inline error) + redline history. Interactions: regenerate draft (prompt_version logged); internal comment; "request send approval" → creates EXTERNAL_COMM approval (send happens only in P14 after quorum).

**P12 Decision Brief `/agent/:id/decision`** — Purpose: the recommendation. Layout: BriefCard (ranked winner + deltas + savings + confidence + coverage) + exception list + evidence appendix pointer + cited NL brief [ELEVATED] (every sentence cited or labeled analytical). Interactions: "request approvals" (routes per policy matrix); print/export preview; reject path back to scenarios with reason.

**P13 Human Approval `/agent/:id/approval`** — Purpose: the gate. Layout: lane-grouped queue (Finance / Compliance / Managerial) with quorum progress, payload-hash card, dry-run summary, expiry countdown, big Approve/Reject (+mandatory reason on reject) — mobile-first at 360px. Interactions: approve → quorum re-evaluated live; expired → re-request; offline queue with conflict warning. Denied: non-lane members see read-only.

**P14 Action Center `/agent/:id/actions`** — Purpose: execute exactly what was approved. Layout: approved-intent queue + DryRunCard each (ALLOW/DENY/NEEDS-APPROVAL, exact payload, recipients, value impact, policy citation) + Execute (idempotent, disabled until ALLOW) + receipts ledger. Interactions: dry-run first (forced), execute → receipt hash; blocked attempts show policy reason + audit link. AGENT-002 enforced here and server-side.

**P15 Run History `/agent/:id/runs`** — Purpose: replayable truth. Layout: run table (trigger, rule_version, tool versions, status ok/degraded/failed, hashes) + step-log viewer + "replay in sandbox" → diff report (match/diverged with field diffs). Interactions: scrub timeline to any run; compare two runs; export run manifest. Degraded runs show AI-unavailable badge, math intact.

**P16 Mission Report `/agent/:id/report`** — Purpose: auditable close. Layout: report composer (sections, format PDF/XLSX/CSV) + completeness checklist (evidence links, approvals, receipts, rule_version) + export history + mission lock banner. Interactions: export → tenant-scoped download; lock → read-only with "reopen as new plan version" path.

### CROSS-CHECK ADD-ON (date 2026-09-24): generic screen-template behaviors binding on all P01–P16

The per-screen specs above exceed the baseline, but the following baseline behaviors apply uniformly to every P-screen and are release-gated alongside the specific layouts: (1) page header with title, breadcrumb, mission/state status, and one primary action; secondary actions live in an overflow menu, never as competing primary buttons; (2) an activity/audit panel is present wherever a material action exists (plan ack, corrections, approvals, dry-runs, executes, exports), reading from the same append-only timeline as P01/P15; (3) all mutations are server-side authorized — client-supplied IDs, prices, supplier status, and extraction values are never trusted and are re-validated against the tenant workspace and pinned versions; (4) material uncertainty is never hidden: thin data, conflicts, stale rates, and hostile flags always render as visible exception content, never as silent defaults; (5) every screen implements all nine states (loading skeleton, empty with next step, partial/incomplete, success, processing, error with safe code, permission-denied, stale, AI-unavailable wherever AI text appears).

## 6. Shared screens G01–G20 (mapped, summarized)

G01 Login (OIDC + MFA, synthetic demo accounts listed) · G02 Recovery (reset flow, no enumeration) · G03 Workspace Picker (membership + budget currency) · G04 Dashboard (portfolio KPIs, my approvals, exception feed) · G05 Notifications (approval-priority inbox, retry/dedupe) · G06 Global Search (missions/docs/suppliers/spans, tenant-scoped) · G07 Documents Library (all mission docs, scan status) · G08 Document Viewer (page/cell view, span highlight, hostile banner) · G09 Suppliers Directory (native master) · G10 Supplier Profile (scorecard + ledger + risks) · G11 Reports (all exports, scope labels) · G12 Report Viewer (PDF/XLSX preview + appendix nav) · G13 Audit Log (filterable hash-chained events, export) · G14 Settings (workspace thresholds, lanes, dial caps) · G15 User/Role Management (invite, lane assignment, deny self-approve) · G16 Rules/Policies (rule_version viewer + tolerance/weight config, dual-control) · G17 AI Run History (all AIJobs, prompts, hashes, degraded flags) · G18 Integrations (provider keys server-side only; ERP/e-sign = roadmap stubs) · G19 Security/Privacy (retention, export scope, session controls) · G20 Error/Not Found (safe messages + request_id + recovery). All implement loading/empty/partial/success/error/denied/stale.

### CROSS-CHECK ADD-ON (date 2026-09-24): shared-screen depth for G13, G16, G17, G18, G19

- **G13 Audit Log `/audit` — full behavior:** filterable DataTable over the append-only hash-chained event store with filters for actor, mission, object type/ID, action, time range, and `request_id` (replay cursor for long missions); row expansion shows before/after hashes and the policy or scan reason; export is tenant-scoped with a manifest of included missions; a dedicated audit-read role can view but never mutate; non-members get the denied state; every material mutation in P01–P16 is verifiable here, and the mission-lock at report state is shown as a terminal banner.
- **G16 Rules/Policies `/settings/rules` — full behavior:** `rule_version` viewer showing weights, tolerances, FX policy, effective-from date, and changelog per version; tolerance/weight configuration is dual-controlled (one lane proposes, a second lane approves) with sandbox impact preview (recomputed bands on current missions, labeled analytical) before activation; policy overrides (coverage waivers, dial increases, threshold exceptions) carry mandatory reason plus expiry and appear in G13; rule changes never rewrite certified past runs — runs stay pinned to their version.
- **G17 AI Run History `/ai-runs` — full behavior:** every AI job row shows purpose, provider, model/prompt/tool versions, input/output hashes, evidence refs in/out, autonomy context (dial + class), latency, token/cost estimate, and status (ok/degraded/blocked/failed) with error codes; degraded runs show the AI-unavailable badge with deterministic results intact; failed jobs offer idempotent retry; the job list is tenant-scoped and exportable for audit; prompt versions are pinned and reproducible from input hash.
- **G18 Integrations `/settings/integrations` — full behavior:** catalog of configured integrations (AI providers with primary + fallback routing; downstream connectors such as ERP/contract/e-sign remain gated roadmap stubs that can only act through approval-checked tools); all credentials live server-side in the secret manager, never in the web bundle, logs, or exports; outbound webhooks use tenant signatures with a replay window and tenant-allowlisted callback hosts; credential rotation and enable/disable are themselves audited approval-tracked actions; a misconfigured integration degrades to a visible banner, never to silent behavior change.
- **G19 Security/Privacy `/settings/security` — full behavior:** per-data-class retention periods (missions, spans, runs, exports) with legal-hold override that suspends deletion; tenant data-deletion and export flows with scope confirmation; data-residency and region-policy display; session controls (MFA status, timeouts, device review); demo-workspace banner (synthetic data only, short retention, no confidential documents, nightly reset); explicit statement that implemented controls alone are not a claim of regulatory compliance — production compliance is jurisdiction- and deployment-specific.

## 7. AI/evidence display rules

AI text always carries a badge (`AI draft`/`AI explanation`/`AI brief`), model + prompt version, timestamp, and citation chips to EvidenceSpans; numbers inside AI text are non-authoritative mirrors of deterministic results (click → source result). During outage: gray "AI unavailable — deterministic math unaffected" card, never silent. Corrections propagate visibly ("re-analysis recommended" chip until re-run).

## 8. Accessibility & responsive

WCAG 2.2 AA; keyboard-complete (palette, drawers, approvals, kanban via list-view toggle); live regions for agent progress/gate blocks; focus trap in drawers/dialogs; 360px approval path; tables collapse to cards under 720px with evidence links preserved; density toggle; reduced-motion support.
