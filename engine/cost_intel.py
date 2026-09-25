"""cost_intel: TCO build-up price+freight+insurance+tooling+tax-discounts (minor units).

Tax modes mirror sourcing_compare. FX rows carry source/time; stale flag when
quoted_at older than tolerance_days in rule tolerances.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from engine.money import FxRate, convert_minor


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)  # naive timestamps are treated as UTC
    return dt


def _stale(quoted_at: str, tolerance_days: int, now: str | None = None) -> bool:
    try:
        q = _parse_dt(quoted_at)
        n = _parse_dt(now) if now else datetime.now(UTC)
        return (n - q).days > tolerance_days
    except (ValueError, TypeError):
        return True


def tco(
    price_minor: int,
    freight_minor: int = 0,
    insurance_minor: int = 0,
    tooling_minor: int = 0,
    tax_minor: int = 0,
    discount_minor: int = 0,
    currency: str = "EUR",
    target_ccy: str = "EUR",
    fx: FxRate | None = None,
    fx_tolerance_days: int = 30,
    fx_now: str | None = None,
) -> dict[str, Any]:
    build_up = {
        "price": price_minor,
        "freight": freight_minor,
        "insurance": insurance_minor,
        "tooling": tooling_minor,
        "tax": tax_minor,
        "discounts": -abs(discount_minor),
    }
    total_src = sum(build_up.values())
    total = (
        convert_minor(total_src, currency, target_ccy, fx) if currency != target_ccy else total_src
    )
    stale = False
    fx_chip = None
    if fx is not None:
        fx_chip = {
            "pair": fx.pair,
            "rate": str(fx.rate),
            "source": fx.source,
            "quoted_at": fx.quoted_at,
        }
        stale = _stale(fx.quoted_at, fx_tolerance_days, fx_now)
    return {"tco_minor": total, "build_up": build_up, "fx": fx_chip, "stale_flag": stale}
