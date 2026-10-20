# ADRs — ProcurementOS-Agent

Architecture Decision Records. **Any deviation from `prerequisite-docs/` is
recorded here, never by silently rewriting the brain.**

Format: `NNNN-title.md` with Status / Context / Decision / Consequences /
Brain refs / Rollback.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-standalone-no-sibling-coupling.md) | Standalone, no sibling coupling | accepted |
| [0002](0002-nextjs-16-security-upgrade.md) | Next.js 16 security upgrade | accepted |
| [0003](0003-ortools-removed-greedy-default.md) | OR-Tools removed; greedy is the certified default | accepted |
| [0004](0004-pyjwt-replaces-python-jose.md) | PyJWT replaces python-jose | accepted |
| [0005](0005-price-uom-normalization.md) | Price-UOM normalisation | accepted |
| [0006](0006-real-timestamp-columns.md) | Real timestamp columns instead of ISO strings in VARCHAR | accepted |
| [0007](0007-evidence-conflicts.md) | Conflicts are detected, not overwritten | accepted |
| [0008](0008-ci-gates-every-push.md) | CI gates every push; the heavy legs stay weekly | accepted |
| [0009](0009-egress-policy.md) | Egress is a policy, not a config value | accepted |
| [0010](0010-observability-and-global-counters.md) | Observability, and the two global counters | accepted |
| [0011](0011-thesis-context-inr-and-evidence-classes.md) | Thesis context: INR, evidence classes, implemented/proposed boundary | accepted |

## Reading order for a reader new to the repository

1. **0008** — why the pipeline is shaped the way it is.
2. **0011** — the research context: currency, identifiers, and the three
   evidence classes that every other document uses.
3. **0006**, **0007** — the two data-model decisions that changed what the
   system can guarantee.
4. **0009**, **0010** — the two control-plane decisions (egress and
   observability) that the release gate's operational boxes depend on.

The evaluation design that the ADR decisions feed is in
[`../EVALUATION.md`](../EVALUATION.md); the works cited are in
[`../REFERENCES.md`](../REFERENCES.md).
