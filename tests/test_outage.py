"""AGENT-004 + ladder/draft + export-scope suites (brain 09)."""

from app.ai import provider as P
from app.negotiation import ladders
from app.reports import exporter
from engine.cost_intel import tco


def test_agent_004_outage_math_exports_intact():
    # Deterministic results are computed WITHOUT the provider...
    r = tco(10000, 1200, 300, 500, 1900, 800)
    assert r["tco_minor"] == 13100
    # ...while AI degrades with no fabrication.
    down = P.MockProvider(down=True)
    res, status = P.run_with_fallback(down, P.MockProvider(down=True), "brief-v1", {"m": "m1"})
    assert res.ok is False and res.degraded is True and status == "degraded"
    assert res.payload == {}  # never fabricated text
    # Recovery replays without recomputing math. A fresh breaker models the
    # post-cooldown probe (B6): within the cooldown window the circuit stays
    # open and calls fail fast to the fallback.
    up = P.MockProvider(down=False)
    res2, status2 = P.run_with_fallback(
        up, P.MockProvider(down=True), "brief-v1", {"m": "m1"}, breaker=P.CircuitBreaker()
    )
    assert res2.ok is True and status2 == "ok"
    assert tco(10000, 1200, 300, 500, 1900, 800)["tco_minor"] == 13100


def test_circuit_breaker_persists_across_calls():
    # B6: the breaker is not per-call — after a failure the circuit opens
    # and the primary is not retried until the cooldown elapses.
    brk = P.CircuitBreaker()
    down = P.MockProvider(down=True)
    P.run_with_fallback(down, P.MockProvider(down=True), "p", {}, breaker=brk)
    assert brk.tripped() is True
    up = P.MockProvider(down=False)
    res, status = P.run_with_fallback(up, P.MockProvider(down=True), "p", {}, breaker=brk)
    assert res.ok is False  # circuit still open: primary never probed
    assert status == "degraded"


def test_schema_fail_twice_then_degraded():
    flaky = P.MockProvider(down=False, fail_schema_times=2)
    res, status = P.run_with_fallback(flaky, P.MockProvider(down=True), "ext-v1", {})
    assert res.degraded is True and res.ok is False  # POS-AI-SCH-01: no silent coerce


def test_ladder_bounds_and_draft_refusal():
    lad = ladders.ladder(candidate_cost_minor=9000, batna_cost_minor=10000)
    assert lad["walk_away"] == 10000 and lad["target"] == 9000
    assert ladders.draft_within_ladder(9500, lad)["within_bounds"] is True
    over = ladders.draft_within_ladder(12000, lad)
    assert over["within_bounds"] is False  # out-of-ladder drafts refused
    # T5: rungs span opening->target and never overshoot below target; the
    # last rung lands exactly on target (E7).
    for c in lad["concessions"]:
        assert lad["target"] <= c <= lad["opening"]
    assert lad["concessions"][-1] == lad["target"]
    # Below target (a better deal than the candidate) is allowed (E8);
    # above walk-away is the hard wall.
    assert ladders.draft_within_ladder(8500, lad)["within_bounds"] is True
    assert ladders.draft_within_ladder(10001, lad)["within_bounds"] is False


def test_ladder_needs_two_steps():
    # T5: steps < 2 raises, never silently returns a degenerate ladder.
    import pytest

    with pytest.raises(ValueError, match=">= 2 steps"):
        ladders.ladder(9000, 10000, steps=1)
    with pytest.raises(ValueError, match=">= 2 steps"):
        ladders.ladder(9000, 10000, steps=0)


def test_pos_exp_01_cross_tenant_export_denied():
    import pytest

    with pytest.raises(exporter.ExportDeniedError):
        exporter.assert_scope("t1", "t2", ["m2"], ["m2"])
    with pytest.raises(exporter.ExportDeniedError):
        exporter.assert_scope("t1", "t1", ["m1", "m2"], ["m1"])
    m = exporter.manifest("t1", ["m1"], "CSV", ["span-1"])
    assert m["watermark"] == "tenant:t1"
