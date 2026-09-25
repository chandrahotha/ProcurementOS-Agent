# ADR-0002 — Next.js 14 → 16.3.6 (security-driven upgrade)

- Status: Accepted
- Date: 2026-09-24

## Context

The brain pins the frontend stack at "Next.js 14 (App Router)"
(`02_ARCHITECTURE.md` §1). The 14.x line carries unpatched advisories —
GitHub flagged criticals on the default branch (issue #7), including
unauthenticated RCE on Windows-hosted dev servers and SSRF via rewrites.
14.2.35 was the last 14.x patch and the alerts remained.

## Decision

Upgrade to Next 16.3.6 via the official `@next/codemod` path, which
brought React 19 and moved params to Promises (`use(props.params)`).
The codemod's Cache-Components opt-outs (`export const instant = false`)
were removed from all 34 pages; Turbopack builds clean without them.

## Consequences

- All security advisories against `next` and its bundled `postcss` clear;
  `npm audit` reports zero for prod and dev.
- No behavior change for this app: every page was already a client
  component reading params; the codemod's transform was mechanical.
- If the brain's stack pin matters to a future integration, the decision
  and its security rationale live here.

## Brain refs

- `02_ARCHITECTURE.md` §1 (stack pin) · issue #7 (dependabot findings)

## Rollback

`git revert` of the upgrade commit restores 14.2.35; the advisories return
with it, so rollback would reopen issue #7.
