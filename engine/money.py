"""Money math: minor-unit integers, Decimal-only, banker's rounding per line then sum.

Conventions (brain 03 §3):
- No float anywhere. FX rows: (pair, rate Decimal(18,8), source, quoted_at).
- FX without source/time rejected. Unknown UOM blocks normalization (never assumed).
- Rounding = banker's (ROUND_HALF_EVEN) per line, then integer sum.
- FX pairs may be quoted in either direction ("USD/EUR" or "EUR/USD"); the
  inverse rate is derived by Decimal division, never float.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

QT = Decimal("1")
RATE_QT = Decimal("0.00000001")  # 8dp, mirrors the rate denomination


def bankers(value: Decimal) -> int:
    return int(value.quantize(QT, rounding=ROUND_HALF_EVEN))


@dataclass(frozen=True)
class FxRate:
    pair: str  # e.g. "USD/EUR" meaning 1 USD = rate EUR
    rate: Decimal
    source: str
    quoted_at: str

    def valid(self) -> bool:
        return (
            bool(self.pair and self.source and self.quoted_at)
            and isinstance(self.rate, Decimal)
            and self.rate > 0
        )


def convert_minor(amount_minor: int, from_ccy: str, to_ccy: str, fx: FxRate | None) -> int:
    if from_ccy == to_ccy:
        return amount_minor
    if fx is None or not fx.valid():
        raise ValueError(f"FX without source/time rejected for {from_ccy}->{to_ccy}")
    expected = f"{from_ccy}/{to_ccy}"
    rate = fx.rate
    if fx.pair != expected:
        inverted = f"{to_ccy}/{from_ccy}"
        if fx.pair != inverted:
            raise ValueError(f"FX pair {fx.pair} does not cover {expected}")
        # Reverse quote: derive the forward rate by division, never float.
        rate = (Decimal("1") / fx.rate).quantize(RATE_QT, rounding=ROUND_HALF_EVEN)
    converted = (Decimal(amount_minor) * rate).quantize(QT, rounding=ROUND_HALF_EVEN)
    return int(converted)


# UOM conversion factors to base unit (versioned source string).
UOM_TABLE: dict[tuple[str, str], Decimal] = {
    ("box", "pcs"): Decimal("24"),  # seed trap: box of 24 pcs
    ("lb", "kg"): Decimal("0.45359237"),
    ("m", "m"): Decimal("1"),
    ("pcs", "pcs"): Decimal("1"),
    ("kg", "kg"): Decimal("1"),
}
UOM_SOURCE = "uom-table-v1"


def normalize_qty(value: str | int | Decimal, uom: str, base_uom: str) -> Decimal:
    if uom == base_uom:
        return Decimal(str(value))
    key = (uom, base_uom)
    factor = UOM_TABLE.get(key)
    if factor is None:
        # Reverse direction: derive by Decimal division (mirrors the FX
        # inversion) — never float.
        rev = UOM_TABLE.get((base_uom, uom))
        if rev is None:
            raise ValueError(f"unknown UOM conversion {uom}->{base_uom}: blocked, never assumed")
        factor = Decimal("1") / rev
    return Decimal(str(value)) * factor
