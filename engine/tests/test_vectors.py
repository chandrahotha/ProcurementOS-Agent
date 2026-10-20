"""Deterministic golden vectors (brain 09 §3). Decimal/minor-unit only."""

from decimal import Decimal

import pytest

from engine import cost_intel, risk_intel, scenario_opt
from engine import sourcing_compare as sc
from engine.money import FxRate, convert_minor, normalize_qty
from engine.supplier_intel import compute_kpis


def test_pos_norm_01_mixed_uom_currency_tax() -> None:
    # Reporting currency is INR; a USD quote is converted at the quoted
    # rate before it can be compared with an INR quote.
    # USD/INR 83.50: 1 USD = 83.50 INR (RBI reference rate).
    fx = FxRate(
        pair="USD/INR", rate=Decimal("83.5"), source="RBI", quoted_at="2026-09-01T00:00:00Z"
    )
    a = sc.QuoteLine("L1", "S-A", Decimal("2"), "box", 1000, "USD", "exclusive", Decimal("0.19"))
    b = sc.QuoteLine("L1", "S-B", Decimal("48"), "pcs", 5000, "INR", "inclusive")
    na = sc.normalize_line(a, "pcs", "INR", fx)
    nb = sc.normalize_line(b, "pcs", "INR", None)
    # A: price is per box -> 2 box x 1000c = 2000 +19% = 2380 USDc
    #    -> 2380 x 83.50 = 198,730 INRc (price_uom honored; ADR-0005)
    # B: 48 pcs x 5000c = 240,000 INRc, tax inclusive
    assert na.normalized_total_minor == 198730
    assert nb.normalized_total_minor == 240000
    ranked = sc.rank_lines([na, nb])
    assert [r.supplier_id for r in ranked] == ["S-A", "S-B"]
    assert sc.savings_vs_baseline(240000, 198730) == 41270


def test_pos_norm_02_unknown_uom_blocks() -> None:
    with pytest.raises(ValueError, match="unknown UOM"):
        normalize_qty(Decimal("1"), "furlong", "pcs")


def test_fx_without_source_rejected() -> None:
    with pytest.raises(ValueError, match="source/time"):
        convert_minor(100, "USD", "INR", None)


def test_pos_tco_01_waterfall() -> None:
    r = cost_intel.tco(10000, 1200, 300, 500, 1900, 800)
    assert r["tco_minor"] == 10000 + 1200 + 300 + 500 + 1900 - 800
    assert r["build_up"]["discounts"] == -800
    assert r["stale_flag"] is False


def test_pos_stale_01_flagged() -> None:
    fx = FxRate("USD/INR", Decimal("83.5"), "RBI", "2020-01-01T00:00:00Z")
    r = cost_intel.tco(100, currency="USD", target_ccy="INR", fx=fx, fx_now="2026-09-24T00:00:00Z")
    assert r["stale_flag"] is True
    assert r["fx"]["source"] == "RBI"


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


# ---- Edge-case vectors (T6): pinned behaviors for the audit fixes ----


def test_per_box_price_honored() -> None:
    # E1/ADR-0005: "2 boxes @ 18.00/box" totals 3600 minor — never 24x-inflated.
    line = sc.QuoteLine("L1", "S-A", Decimal("2"), "box", 1800, "INR", "inclusive")
    n = sc.normalize_line(line, "pcs", "INR", None)
    assert n.normalized_total_minor == 3600


def test_price_uom_conversion() -> None:
    # Price quoted per box, quantity in pcs: the qty converts into the price
    # UOM before multiplying.
    line = sc.QuoteLine(
        "L1", "S-A", Decimal("48"), "pcs", 1800, "INR", "inclusive", price_uom="box"
    )
    n = sc.normalize_line(line, "pcs", "INR", None)
    # 48 pcs = 2 boxes x 1800 = 3600 minor.
    assert n.normalized_total_minor == 3600


def test_duplicate_lines_cheapest_kept() -> None:
    # E2: duplicate (line, supplier) pairs flag all but the cheapest.
    a = sc.QuoteLine("L1", "S-A", Decimal("1"), "pcs", 500, "INR", "inclusive")
    b = sc.QuoteLine("L1", "S-A", Decimal("1"), "pcs", 400, "INR", "inclusive")
    normed = sc.compare_lines([a, b], "pcs", "INR", None)
    kept = [n for n in normed if n.compliant]
    flagged = [n for n in normed if not n.compliant]
    assert len(kept) == 1 and kept[0].normalized_total_minor == 400
    assert len(flagged) == 1 and any("duplicate" in x for x in flagged[0].notes)


def test_expired_validity_noncompliant() -> None:
    # E2: a quote valid until 2020 ranks non-compliant with a recorded note.
    line = sc.QuoteLine(
        "L1", "S-A", Decimal("1"), "pcs", 500, "INR", "inclusive", valid_until="2020-01-01"
    )
    normed = sc.compare_lines([line], "pcs", "INR", None, today="2026-09-25")
    assert normed[0].compliant is False
    assert any("expired" in x for x in normed[0].notes)
    ranked = sc.rank_lines(normed)
    assert ranked[0].rank == 0  # non-compliant: unranked, excluded from award math


def test_rank_ties_break_by_line_id() -> None:
    # E11: ties are deterministic regardless of input order.
    a = sc.QuoteLine("L2", "S-A", Decimal("1"), "pcs", 500, "INR", "inclusive")
    b = sc.QuoteLine("L1", "S-B", Decimal("1"), "pcs", 500, "INR", "inclusive")
    r1 = sc.rank_lines(
        [sc.normalize_line(a, "pcs", "INR", None), sc.normalize_line(b, "pcs", "INR", None)]
    )
    r2 = sc.rank_lines(
        [sc.normalize_line(b, "pcs", "INR", None), sc.normalize_line(a, "pcs", "INR", None)]
    )
    assert [n.line_id for n in r1] == [n.line_id for n in r2] == ["L1", "L2"]


def test_composite_101_band_is_critical_no_crash() -> None:
    # E3: composite >= 101 never raises StopIteration — band is CRITICAL.
    s = risk_intel.score(
        {"quality": 101, "delivery": 101, "financial": 101, "compliance": 101, "geo": 101}
    )
    assert s["band"] == "CRITICAL"
    assert risk_intel.band_for(500) == "CRITICAL"


def test_allocate_rejects_negative_and_zero_supplier_cap() -> None:
    # E4: negative costs raise; max_suppliers=0 is infeasible, not ignored.
    import pytest

    with pytest.raises(ValueError, match="negative"):
        scenario_opt.allocate(100, [{"supplier_id": "S1", "unit_cost_minor": -50, "capacity": 100}])
    r = scenario_opt.allocate(
        100, [{"supplier_id": "S1", "unit_cost_minor": 50, "capacity": 100}], max_suppliers=0
    )
    assert r["constraints_ok"] is False


def test_allocate_single_supplier_zero_demand() -> None:
    # T6 edge: zero demand allocates nothing (constraints trivially ok).
    r = scenario_opt.allocate(0, [{"supplier_id": "S1", "unit_cost_minor": 50, "capacity": 100}])
    assert r["allocations"] == [] and r["objective_value"] == 0


def test_reverse_fx_pair_inverts() -> None:
    # E10: a reverse quote (INR/USD held, USD->INR needed) inverts via
    # Decimal. The held rate 0.01197605 is 1/83.5 to 8dp, so the derived
    # forward rate is 83.49998539 and 1000 USDc converts to 83,500 INRc.
    fx = FxRate(
        pair="INR/USD", rate=Decimal("0.01197605"), source="RBI", quoted_at="2026-09-01T00:00:00Z"
    )
    assert convert_minor(1000, "USD", "INR", fx) == 83500


def test_naive_fx_timestamp_not_always_stale() -> None:
    # E5: naive quoted_at is treated as UTC — a fresh rate is not stale.
    from engine.cost_intel import _stale

    assert _stale("2026-09-24T00:00:00", 30, now="2026-09-25T00:00:00") is False


def test_stale_fx_tco_never_certifies_award() -> None:
    # T17 (engine side): the composite path refuses when every cost row is
    # stale — the API-level filter pins the refusal end to end.
    from engine.cost_intel import tco

    r = tco(
        100,
        currency="USD",
        target_ccy="INR",
        fx=FxRate("USD/INR", Decimal("83.5"), "RBI", "2020-01-01T00:00:00Z"),
        fx_now="2026-09-25T00:00:00Z",
    )
    assert r["stale_flag"] is True
