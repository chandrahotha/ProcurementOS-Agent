"""Deterministic golden vectors (brain 09 §3). Decimal/minor-unit only."""

from decimal import Decimal

import pytest

from engine import cost_intel, risk_intel, scenario_opt
from engine import sourcing_compare as sc
from engine.money import FxRate, convert_minor, normalize_qty
from engine.supplier_intel import compute_kpis


def test_pos_norm_01_mixed_uom_currency_tax() -> None:
    fx = FxRate(
        pair="USD/EUR", rate=Decimal("0.92"), source="ECB", quoted_at="2026-09-01T00:00:00Z"
    )
    a = sc.QuoteLine("L1", "S-A", Decimal("2"), "box", 1000, "USD", "exclusive", Decimal("0.19"))
    b = sc.QuoteLine("L1", "S-B", Decimal("48"), "pcs", 90, "EUR", "inclusive")
    na = sc.normalize_line(a, "pcs", "EUR", fx)
    nb = sc.normalize_line(b, "pcs", "EUR", None)
    # A: 2 box = 48 pcs x 1000c = 48000 +19% = 57120 USDc -> EUR 52550.4 -> 52550
    assert na.normalized_total_minor == 52550
    assert nb.normalized_total_minor == 4320
    ranked = sc.rank_lines([na, nb])
    assert [r.supplier_id for r in ranked] == ["S-B", "S-A"]
    assert sc.savings_vs_baseline(52550, 4320) == 48230


def test_pos_norm_02_unknown_uom_blocks() -> None:
    with pytest.raises(ValueError, match="unknown UOM"):
        normalize_qty(Decimal("1"), "furlong", "pcs")


def test_fx_without_source_rejected() -> None:
    with pytest.raises(ValueError, match="source/time"):
        convert_minor(100, "USD", "EUR", None)


def test_pos_tco_01_waterfall() -> None:
    r = cost_intel.tco(10000, 1200, 300, 500, 1900, 800)
    assert r["tco_minor"] == 10000 + 1200 + 300 + 500 + 1900 - 800
    assert r["build_up"]["discounts"] == -800
    assert r["stale_flag"] is False


def test_pos_stale_01_flagged() -> None:
    fx = FxRate("USD/EUR", Decimal("0.9"), "ECB", "2020-01-01T00:00:00Z")
    r = cost_intel.tco(100, currency="USD", target_ccy="EUR", fx=fx, fx_now="2026-09-24T00:00:00Z")
    assert r["stale_flag"] is True
    assert r["fx"]["source"] == "ECB"


def test_pos_risk_01_thin_and_bands() -> None:
    k = compute_kpis([{"on_time": True, "accepted": True, "qty": 10, "defects": 0}] * 2)
    assert k["thin"] is True
    s = risk_intel.score(
        {"quality": 10, "delivery": 10, "financial": 10, "compliance": 10, "geo": 10}
    )
    assert (s["composite"], s["band"]) == (10, "LOW")
    s2 = risk_intel.score(
        {"quality": 90, "delivery": 90, "financial": 90, "compliance": 90, "geo": 90}
    )
    assert s2["band"] == "CRITICAL"


def test_pos_scen_01_infeasible_with_hints() -> None:
    r = scenario_opt.allocate(100, [{"supplier_id": "S1", "unit_cost_minor": 50, "capacity": 40}])
    assert r["constraints_ok"] is False
    assert any("capacity" in n or "shortfall" in n for n in r["notes"])
    ok = scenario_opt.allocate(
        100,
        [
            {"supplier_id": "S1", "unit_cost_minor": 60, "capacity": 60},
            {"supplier_id": "S2", "unit_cost_minor": 50, "capacity": 60},
        ],
    )
    assert ok["constraints_ok"] is True
    assert ok["objective_value"] == 60 * 50 + 40 * 60


def test_bankers_rounding_per_line() -> None:
    # 0.5 rounds to even: 2.5 -> 2, 3.5 -> 4
    from engine.money import bankers

    assert bankers(Decimal("2.5")) == 2
    assert bankers(Decimal("3.5")) == 4
