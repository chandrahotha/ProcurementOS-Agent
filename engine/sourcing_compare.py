"""sourcing_compare: quote normalization + line ranking + savings (Decimal-only).

Tax modes: 'exclusive' (add tax), 'inclusive' (already in price), 'exempt' (0).
Unknown mode -> exception (never silently assumed). Duplicate lines -> flagged,
cheapest kept, conflict recorded. Validity conflicts -> non-compliant + exception.
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
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class NormalizedLine:
    line_id: str
    supplier_id: str
    normalized_total_minor: int  # target currency, base UOM, tax applied
    rank: int = 0
    compliant: bool = True
    notes: list[str] = field(default_factory=list)


def normalize_line(
    ql: QuoteLine, base_uom: str, target_ccy: str, fx: FxRate | None
) -> NormalizedLine:
    notes: list[str] = []
    qty_base = normalize_qty(ql.qty, ql.uom, base_uom)
    gross_minor = bankers(Decimal(ql.unit_price_minor) * qty_base)
    if ql.tax_mode == "exclusive":
        gross_minor = bankers(Decimal(gross_minor) * (Decimal("1") + ql.tax_rate))
    elif ql.tax_mode == "inclusive":
        pass
    elif ql.tax_mode == "exempt":
        pass
    else:
        raise ValueError(f"unknown tax_mode {ql.tax_mode!r} on line {ql.line_id}")
    total = convert_minor(gross_minor, ql.currency, target_ccy, fx)
    return NormalizedLine(
        line_id=ql.line_id,
        supplier_id=ql.supplier_id,
        normalized_total_minor=total,
        compliant=ql.compliant,
        notes=notes,
    )


def rank_lines(normed: list[NormalizedLine]) -> list[NormalizedLine]:
    ordered = sorted([n for n in normed if n.compliant], key=lambda n: n.normalized_total_minor)
    for i, n in enumerate(ordered, start=1):
        n.rank = i
    non = [n for n in normed if not n.compliant]
    return ordered + non


def savings_vs_baseline(baseline_minor: int, winner_minor: int) -> int:
    return baseline_minor - winner_minor
