# Frontend Findings (F1–F72) — web/

Status: `[ ]` open · `[x]` fixed · `[~]` deferred with ADR.

## Load-bearing e2e hooks (must survive all fixes)

`main[data-screen='P01'…'P16']` · `role="status"` texts: "clean", "tasks", "Advanced to plan.", "8 spans recorded", "Version 1", "Quorum met", "ALLOW", "Executed.", "settled", "Exported", "Winner", "managerial", "objective", "Draft stored", "complete" · `.gate-grid` buttons: "Create mission", "Export" · `.row` buttons: "Generate plan", "Acknowledge plan", "Request approvals", "Dry-run", "Execute", "Mark actions settled" · `.approval-card` + "Approve" · `table tbody tr` counts (2 suppliers after analysis) · `input[type=file]` · `getByLabel("Title")` · `pos_token` localStorage key.

## Bugs

- [x] **F1** `Screen` primary renders a dead `<button>` with no onClick — 18 instances. `components/Screen.tsx:40`. → Accept `onClick`/`href`; wire call sites; keep label text.
- [x] **F2** Nine documented states: `partial`, `processing`, `stale` have no render branch. `components/Screen.tsx:42-47`. → Add visual branches.
- [x] **F3** CommandPalette mounted only on P01 — Cmd+K works on one page. `components/CommandPalette.tsx`, `app/agent/page.tsx:55`. → Mount in root layout.
- [x] **F4** `missionId` never passed — 3 `__mission__` items silently no-op. `components/CommandPalette.tsx:17,36-37`. → Supply from mission context; hide when no mission.
- [x] **F5** Comment says "/"-focus handler exists; none does. `components/CommandPalette.tsx:2`. → Implement or fix comment.
- [x] **F6** `kpis` state declared+rendered but `setKpis` never called. `app/agent/[id]/suppliers/page.tsx:36,73`. → Wire from run summary or delete.
- [x] **F7** `dryRun()` no try/catch + `JSON.parse(payload)` can throw SyntaxError. `app/agent/[id]/actions/page.tsx:23-31`. → Guard + alert.
- [x] **F8** `body.payload = JSON.parse(payload)` outside try block. `components/AdvancePanel.tsx:27-31`. → Move inside try.
- [x] **F9** EvidenceDrawer `correct()` no catch — unhandled rejection. `components/EvidenceDrawer.tsx:22-33`. → try/catch, surface error, close only on success.
- [x] **F10** Drawer `value` never reset between spans — correction applies span A's text to span B. `components/EvidenceDrawer.tsx:19,49-53`. → `key={span.id}` or effect reset.
- [x] **F11** Stale ALLOW keeps Execute enabled after changing actionClass/tool/payload. `app/agent/[id]/actions/page.tsx:14-15,29-47`. → Clear verdict on change.
- [x] **F12** Execute idempotency key omits payload hash — changed payload gets original receipt. `app/agent/[id]/actions/page.tsx:39`. → Derive key from payload hash.
- [x] **F13** Retry key `web-${key}-${Date.now()}` unique per call — defeats idempotency. `app/agent/[id]/tasks/page.tsx:32`. → Stable key.
- [x] **F14** Advance/decide no busy state — double-submit. `components/AdvancePanel.tsx:60`, `app/agent/[id]/approval/page.tsx:66-69`. → busy + disabled.
- [x] **F15** P01 connect form hidden after 401/403 — no way to replace token. `app/agent/page.tsx:56,32-38`. → Render form in denied/error states.
- [x] **F16** All fetch effects lack abort/stale-response guards — fast navigation renders wrong mission's data. 13 effects. → AbortController + latest-wins.
- [x] **F17** `res.json()` unconditional — non-JSON 502 body throws raw SyntaxError. `lib/api-client.ts:46,94`. → text-first + guarded decode.
- [x] **F18** No `/agent/[id]` page — mission deep-links 404. → Add mission overview linking all 14 screens.
- [x] **F19** Error mapping lossy: intake swallows all errors; tasks/suppliers/scenarios/runs/decision map 500→empty; audit/rules map 500→denied. → Branch on `ApiError.status` in shared hook.
- [x] **F20** No 401 handling — no token clear + redirect to login. → Shared wrapper.
- [x] **F21** `quickFill()` documents call outside try. `app/agent/[id]/evidence/page.tsx:40-44`. → Move inside try.
- [x] **F22** Quick-fill writes fake values ("12.40" ×8) into real evidence store; Suppliers sends hardcoded DEMO_PAYLOAD — pollutes certified results in non-seeded envs. → Gate behind dev-mode flag.
- [x] **F23** ExceptionBanner: dead anchors (`#here` ×3), self-link, permanently-dead banner (`count={0}`). `app/agent/[id]/{suppliers,cost,risk}/page.tsx`, `app/agent/page.tsx:72`. → Real element ids / Next Link; delete dead banner.
- [x] **F24** `plan!.version` non-null assertions. `app/agent/[id]/plan/page.tsx:33-34`. → Guard.
- [x] **F25** Ineffective inline `/* eslint-disable-next-line */` comments (nothing disabled). `intake:24`, `tasks:28`, `evidence:37-38`. → Fix or restructure.
- [x] **F26** Smoke test depends on dead header "Approve" button being sole match on denied approval page (latent strict-mode violation when real approvals render). `e2e/smoke.spec.ts:15`. → Scope test + keep visible button in denied state.

## UX / product gaps (stub pages → real screens)

- [x] **F27** `/dashboard` (G04): bare shell → real KPI dashboard (state distribution, low-coverage, recent events from `api.missions` + `api.audit`, links to `/agent/<id>`).
- [x] **F28** `/login` (G01): no form at all → real login (token form + persona quick-select + `?next=` redirect; 401s route here).
- [x] **F29** `/analytics` (AN): bare shell → cross-mission aggregates from `GET /missions`.
- [x] **F30** `/documents` (G07): bare shell → tenant documents (aggregate `api.documents` across missions; links to `/documents/[docId]`).
- [x] **F31** `/documents/[docId]` (G08): bare shell → real viewer (doc + spans + quarantine verdict).
- [x] **F32** `/notifications` (G05): bare shell, no backend resource → notifications resource (approvals pending, gate rejections, task blocks) + screen.
- [x] **F33** `/recovery` (G02): bare shell → replay-failure triage + guided retry.
- [x] **F34** `/reports` (G11): bare shell → export history from audit events.
- [x] **F35** `/reports/[reportId]` (G12): orphaned bare shell → report viewer or remove.
- [x] **F36** `/search` (G06): bare shell → real search (missions/suppliers/documents) wired to palette.
- [x] **F37** `/suppliers` (G09): bare shell, no directory endpoint → backend directory + screen with filters.
- [x] **F38** `/suppliers/[supplierId]` (G10): orphaned → profile from aggregated KPIs.
- [x] **F39** `/workspaces` (G03): bare shell but `GET /workspaces` exists → wire it (picker + mission counts).
- [x] **F40** `/templates` (TPL): bare shell, P02 is template-less → template picker or remove.
- [x] **F41** `/settings` (G14): bare shell → settings index with cards to sub-pages.
- [x] **F42** `/settings/{users,security,integrations}` (G15/G19/G18): bare shells + dead header buttons ("Rotate credential", "Review sessions") → real management screens.
- [x] **F43** No global app shell — layout renders `<body>{children}</body>` bare: no sidebar/topbar, no nav, no user/token indicator. → Persistent shell so no route is URL-only.
- [x] **F44** No mission-scoped navigation — 14 mission screens unreachable from each other (only 3 cross-links in whole app). → Shared `[id]` layout with tabs/stepper.
- [x] **F45** Breadcrumbs plain text, no links/aria-current. `components/Screen.tsx:36`. → Linked ol.
- [x] **F46** No KPI cards on mission control — raw table only. `app/agent/page.tsx:69-88`. → Summary cards.
- [x] **F47** Tables have no sort/filter/pagination anywhere; backend supports `?state=` and `?limit=` but client never passes either. → Client-side sort/filter + query params.
- [x] **F48** No loading/optimistic feedback on any mutation. → Shared busy-state hook.
- [x] **F49** Command palette minimal: 6 items, no grouping, no recent missions, no arrow-key navigation. → Expand.
- [x] **F50** No keyboard shortcuts beyond Cmd+K (no `/`, no A/R on approval, Escape only in palette not drawer). → Shortcut map + hints.
- [x] **F51** `api.timeline()` defined but never used. `lib/api-client.ts:156-158`. → Timeline panel on mission overview.
- [x] **F52** Plan diff endpoint unused (`GET /missions/{id}/plans/{version}/diff`). → Client method + version selector on P04.
- [x] **F53** `PATCH /missions/{id}` unused — title/budget/autonomy not editable anywhere. → Client method + mission-settings panel.

## Accessibility

- [x] **F54** EvidenceDrawer `role="dialog"` without aria-modal/focus trap/Escape/scroll lock. `components/EvidenceDrawer.tsx:35`. → Full dialog treatment.
- [x] **F55** CommandPalette `role="dialog"` without aria-modal/roving selection/focus return. `components/CommandPalette.tsx:42-53`. → Full dialog treatment.
- [x] **F56** Breadcrumb nav text-only, no aria-current. `components/Screen.tsx:36`. → (see F45)
- [x] **F57** No table has caption; no th has scope="col". → Add to all.
- [x] **F58** Spans table empty `<th></th>` unnamed header. `app/agent/[id]/evidence/page.tsx:77`. → sr-only text.
- [x] **F59** No [disabled] button style — gated Execute indistinguishable. `app/globals.css:72-74`. → Add.
- [x] **F60** Dark mode keeps light tone tokens — `[data-tone="ok"]` #15803d on #0b1220 fails contrast (~2.4:1). `app/globals.css:19-26`. → Override tone tokens in .dark.
- [x] **F61** Multiple role="status" regions per page — redundant announcements. → Consolidate/clear prior note.

## Design system

- [x] **F62** `.board`, `.col`, `.card`, `.stale-row` used in markup but never defined in CSS — task board unstyled. `app/agent/[id]/tasks/page.tsx:50-56` etc. → Define.
- [x] **F63** Inter + IBM Plex Mono referenced via CSS vars but never loaded (no next/font). `app/globals.css:16-17`, `app/layout.tsx`. → Load both.
- [x] **F64** `.dark` tokens + `.density-*` classes dead: nothing applies them, no toggle UI. → Theme toggle (persisted) or remove.
- [x] **F65** No skeletons — loading state is bare `aria-busy` text. → Skeleton primitives per state.
- [x] **F66** Responsive minimal: only 720px table collapse hides thead with no per-row labels; no max-width container. → `td::before { content: attr(data-label) }` pattern + container.
- [x] **F67** No per-page metadata/icons/viewport/favicon. `app/layout.tsx:3-6`. → Add.

## Consistency

- [x] **F68** ScreenState union duplicated verbatim in Screen.tsx + api-client.ts. → Shared types module.
- [x] **F69** Loading strategy inconsistent per screen (explicit loading vs derive-from-length vs hardcoded success). → One loading hook everywhere.
- [x] **F70** Breadcrumb separator style differs (P02 "Mission Control / New" vs mission screens "Mission / Intake"). → One convention + helper.
- [x] **F71** P01 convoluted state ternary (types already compatible). `app/agent/page.tsx:54`. → Pass directly.
- [x] **F72** Hand-rolled markup everywhere instead of shared Table/Field/JsonBlock primitives; index-based React keys (`key={i}` ×3). → Extract primitives; stable keys.

## Data plumbing

- [x] **F73** Missing client methods: plan diff, PATCH mission, timeline (never called), `?state=`/`?limit=` filters never passed. → Add + wire.
- [x] **F74** Browser calls API directly with CORS; no route handlers/rewrites proxy exist (comment claims production uses session cookie path). `lib/api-client.ts:4`, `next.config.mjs`. → `/api/v1` rewrite.
- [x] **F75** Token in localStorage, no expiry awareness. → Store expiry, route to /login.
- [x] **F76** `get()` sends Idempotency-Key on GET (meaningless). → Drop.
- [x] **F77** Client types vs payloads: tasks type drops `plan_version`; Run omits `tool_versions`. → Reconcile + surface.
- [x] **F78** No error.tsx / not-found.tsx / loading.tsx anywhere — uncaught render error crashes app; bad id gets default 404. → Add all three.
- [x] **F79** No middleware.ts — protected routes publicly reachable. → Auth check + redirect.
