"""sourcing_compare: quote normalization + line ranking + savings (Decimal-only).

Tax modes: 'exclusive' (add tax), 'inclusive' (already in price), 'exempt' (0).
Unknown mode -> exception (never silently assumed).

Line totals honor the price denomination: `price_uom` names the UOM the unit
price is quoted in (empty = same as `uom`). The quantity is converted into the
price UOM before multiplying, so "2 boxes @ 18.00/box" totals 3600 minor —
never 24x-inflated by converting the qty but not the price.

Tax is applied to the exact unrounded product; a single banker's rounding
lands at the end (per line), then FX converts.

Duplicate lines (same line_id + supplier_id) -> all but the cheapest flagged
non-compliant with a recorded note. Expired `valid_until` (vs the provided
ISO date) -> non-compliant with a recorded note.

Ranking is deterministic: ties break by line_id regardless of input order;
non-compliant lines share rank 0 (unranked, excluded from award math).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from engine.money import FxRate, bankers, convert_minor, normalize_qty


@dataclass
class QuoteLine:
    line_id: str
    supplier_id: str
    qty: Decimal
    uom: str
    unit_price_minor: int
    currency: str
    tax_mode: str  # exclusive | inclusive | exempt
    tax_rate: Decimal = Decimal("0")
    compliant: bool = True
    valid_until: str = ""
    price_uom: str = ""  # UOM the unit price is denominated in; "" = same as uom
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class NormalizedLine:
    line_id: str
    supplier_id: str
    normalized_total_minor: int  # target currency, line total, tax applied
    rank: int = 0
    compliant: bool = True
    notes: list[str] = field(default_factory=list)


def normalize_line(
    ql: QuoteLine, base_uom: str, target_ccy: str, fx: FxRate | None
) -> NormalizedLine:
    qty_price_uom = _qty_in_price_uom(ql)
    exact = Decimal(ql.unit_price_minor) * qty_price_uom
    if ql.tax_mode == "exclusive":
        exact = exact * (Decimal("1") + ql.tax_rate)
    elif ql.tax_mode not in ("inclusive", "exempt"):
        raise ValueError(f"unknown tax_mode {ql.tax_mode!r} on line {ql.line_id}")
    gross_minor = bankers(exact)
    total = convert_minor(gross_minor, ql.currency, target_ccy, fx)
    return NormalizedLine(
        line_id=ql.line_id,
        supplier_id=ql.supplier_id,
        normalized_total_minor=total,
        compliant=ql.compliant,
        notes=[],
    )


def _qty_in_price_uom(ql: QuoteLine) -> Decimal:
    """Quantity expressed in the UOM the unit price is denominated in."""
    price_uom = ql.price_uom or ql.uom
    return normalize_qty(ql.qty, ql.uom, price_uom)


def compare_lines(
    qls: list[QuoteLine],
    base_uom: str,
    target_ccy: str,
    fx: FxRate | None,
    today: str = "",
) -> list[NormalizedLine]:
    """Normalize, then flag duplicates + expired quotes. `today` is an ISO date."""
    normed = [normalize_line(q, base_uom, target_ccy, fx) for q in qls]
    for q, n in zip(qls, normed, strict=True):
        if q.valid_until and today and q.valid_until < today:
            n.compliant = False
            n.notes.append(f"quote expired {q.valid_until}")
    groups: dict[tuple[str, str], list[NormalizedLine]] = {}
    for n in normed:
        groups.setdefault((n.line_id, n.supplier_id), []).append(n)
    for group in groups.values():
        if len(group) > 1:
            keep = min(group, key=lambda n: n.normalized_total_minor)
            for n in group:
                if n is not keep:
                    n.compliant = False
                    n.notes.append("duplicate line: cheapest kept")
    return normed


def rank_lines(normed: list[NormalizedLine]) -> list[NormalizedLine]:
    ordered = sorted(
        [n for n in normed if n.compliant],
        key=lambda n: (n.normalized_total_minor, n.line_id, n.supplier_id),
    )
    for i, n in enumerate(ordered, start=1):
        n.rank = i
    non = [n for n in normed if not n.compliant]
    return ordered + non


def savings_vs_baseline(baseline_minor: int, winner_minor: int) -> int:
    return baseline_minor - winner_minor
