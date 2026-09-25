# ADR-0005 — Quote-line totals honor the price denomination (price_uom)

- Status: Accepted
- Date: 2026-09-25

## Context

The golden vector `POS-NORM-01` encoded the old normalization math: it
converted the quantity to base units but multiplied the unit price
unchanged, implicitly assuming every price is quoted per base unit. The
seed's own fixture ("2 boxes of 24 pcs, EUR 18.00/box") proves the
assumption wrong: the old math returned 86400 minor where the true line
total is 3600 minor — a silent 24× inflation. A per-box price is the
norm in real procurement quotes, so the engine under-counted or
over-counted depending on pack size, and every downstream ranking,
TCO, and award value inherited the error.

## Decision

`QuoteLine` gains an explicit `price_uom` field (empty = same as `uom`).
`normalize_line` converts the quantity into the price UOM before
multiplying, applies tax to the exact unrounded product, and lands a
single banker's rounding at the end. The golden vector is updated to the
corrected semantics (2000 minor +19% → 2190 EUR minor) and the old value
is recorded here as the bug it was. Duplicate-line flagging and
`valid_until` expiry checks are implemented alongside (`compare_lines`),
closing the gap the old docstring promised but the code never delivered.

## Consequences

- Per-box pricing normalizes correctly; totals, rankings, TCO, and award
  values inherit correct math.
- `POS-NORM-01` changes value (52550 → 2190 for line A) — this ADR is the
  deviation record required by the brain's "do not edit during
  implementation" rule.
- Analyze payloads may now carry `price_uom` per quote line; omitted
  means "same as `uom`", which is backward compatible.

## Brain refs

- `03_DETERMINISTIC_ENGINE.md` §3 (money conventions) — the price
  denomination rule was implied ("never assumed") but never implemented.

## Rollback

Restore the old multiply order and the old golden value — not
recommended: it silently mis-prices per-box quotes.
