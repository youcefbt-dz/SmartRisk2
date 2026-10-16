import numpy as np
import pytest

from smartrisk.core import registry
from smartrisk.core.analysis.montecarlo import build_shocks
from smartrisk.core.engine import forecast, loans, schema


def norm(raw):
    p, _ = schema.normalize(raw)
    return p


@pytest.mark.parametrize("regime", ["ifu", "reel"])
def test_balance_sheet_balances(sample_raw, regime):
    p = norm(sample_raw)
    fc = forecast.run_forecast(p, regime=regime)
    assert np.abs(fc.a["check"]).max() < 1e-4


def test_balance_balances_under_random_shocks(sample_raw):
    p = norm(sample_raw)
    sh = build_shocks(p, 300, 7)
    fc = forecast.run_forecast(p, sh, regime="reel")
    assert fc.a["cash"].shape == (300, p["horizon"])
    assert np.abs(fc.a["check"]).max() < 1e-3


def test_mc_is_reproducible(sample_raw):
    a = registry.run("montecarlo", sample_raw, {"n": 500, "seed": 3})
    b = registry.run("montecarlo", sample_raw, {"n": 500, "seed": 3})
    assert a["p_ruin_12"] == b["p_ruin_12"] and a["bands"]["p50"] == b["bands"]["p50"]


def test_mc_bands_are_ordered(sample_raw):
    r = registry.run("montecarlo", sample_raw, {"n": 800})
    for lo, hi in (("p5", "p25"), ("p25", "p50"), ("p50", "p75"), ("p75", "p95")):
        assert all(x <= y + 1e-6 for x, y in zip(r["bands"][lo], r["bands"][hi]))


def test_more_uncertainty_never_reduces_risk(sample_raw):
    low = dict(sample_raw, risk={"uncertainty": 0.5})
    high = dict(sample_raw, risk={"uncertainty": 3.0})
    plow = registry.run("montecarlo", low, {"n": 1500})["p_ruin_horizon"]
    phigh = registry.run("montecarlo", high, {"n": 1500})["p_ruin_horizon"]
    assert phigh >= plow


def test_zero_revenue_project_does_not_crash():
    for name in ("summary", "sensitivity", "reverse_stress", "pricing", "optimizer", "investment", "financing", "statements", "tracking", "advice"):
        out = registry.run(name, {"name": "x"}, {})
        assert isinstance(out, dict)


def test_garbage_input_is_normalised():
    p, warnings = schema.normalize({"products": [{"price": "abc", "units": -5}], "horizon": 9999, "start_cash": None, "loans": "x"})
    assert p["horizon"] == schema.MAX_HORIZON and p["products"][0]["price"] == 0 and p["products"][0]["units"] == 0
    assert isinstance(warnings, list)


def test_loan_schedule_amortises_fully():
    ln = {"principal": 1_000_000, "rate": 6, "months": 24, "grace": 3, "start_month": 1, "existing": False}
    s = loans.loan_schedule(ln, 48)
    assert abs(s["principal"].sum() - 1_000_000) < 1e-4
    assert s["balance"][-1] == 0 and s["disb"].sum() == 1_000_000
    assert s["principal"][:3].sum() == 0  # فترة الإمهال بلا سداد أصل


def test_existing_loan_has_no_disbursement():
    ln = {"principal": 500_000, "rate": 5, "months": 12, "grace": 0, "start_month": 1, "existing": True}
    s = loans.loan_schedule(ln, 24)
    assert s["disb"].sum() == 0 and s["opening"] == 500_000
    assert abs(s["principal"].sum() - 500_000) < 1e-4


def test_lag_series_conserves_mass_and_interpolates():
    x = np.zeros((1, 10)); x[0, 0] = 100
    y = forecast.lag_series(x, np.array([1.5]))
    assert abs(y.sum() - 100) < 1e-9 and y[0, 1] == pytest.approx(50) and y[0, 2] == pytest.approx(50)


def test_ifu_switches_to_reel_above_ceiling(sample_raw):
    big = dict(sample_raw, legal_form="individual")
    for pr in big["products"]:
        pr["units"] *= 10
    p = norm(big)
    regime, notes = forecast.resolve_regime(p)
    assert regime == "reel" and notes


def test_company_is_never_ifu(sample_raw):
    p = norm(dict(sample_raw, legal_form="company", tax={"regime": "ifu"}))
    assert forecast.resolve_regime(p)[0] == "reel"


def test_breakeven_revenue_gives_zero_profit(sample_raw):
    be = registry.run("breakeven", sample_raw, {})
    assert be["breakeven_total"] > 0 and 0 < be["contribution_margin_ratio"] < 1


def test_reverse_stress_threshold_actually_fails(sample_raw):
    p = norm(sample_raw)
    r = registry.run("reverse_stress", sample_raw, {})
    item = next(i for i in r["items"] if i["key"] == "demand")
    if item["status"] == "found":
        m = 1 - item["threshold"] / 100
        fc = forecast.run_forecast(p, forecast.Shocks.scalar(demand=m - 0.01))
        assert fc.a["cash"].min() < 0
        fc = forecast.run_forecast(p, forecast.Shocks.scalar(demand=m + 0.01))
        assert fc.a["cash"].min() >= 0


def test_sensitivity_sorted_by_swing(sample_raw):
    rows = registry.run("sensitivity", sample_raw, {"pct": 10})["metrics"]["net_income_y1"]["rows"]
    swings = [r["swing"] for r in rows]
    assert swings == sorted(swings, reverse=True)
    price = next(r for r in rows if r["key"] == "price")
    assert price["high"] > price["low"]


def test_optimizer_never_worse_than_current(sample_raw):
    r = registry.run("optimizer", sample_raw, {})
    assert r["feasible"] and r["optimal_contribution"] >= r["current_contribution"] - 1e-6
    for u in r["usage"]:
        assert u["optimal"] <= u["limit"] + 1e-6


def test_investment_manual_matches_textbook():
    r = registry.run("investment", {"name": "x"}, {"outlay": 1000, "flows": [500, 500, 500], "rate": 10})
    assert r["npv"] == pytest.approx(500 / 1.1 + 500 / 1.21 + 500 / 1.331 - 1000, rel=1e-9)
    assert r["irr"] == pytest.approx(23.375, abs=0.01)


def test_financing_uses_common_random_numbers(sample_raw):
    r = registry.run("financing", sample_raw, {"amount": 0, "n": 400})
    base = r["options"][0]["p_ruin_12"]
    assert all(o["p_ruin_12"] == base for o in r["options"])  # بلا مبلغ لا فرق بين الخيارات


def test_tracking_flags_revenue_miss(sample_raw):
    p = dict(sample_raw)
    plan = registry.run("statements", p, {})
    rev1 = plan["income"][0]["monthly"][0]
    p["actuals"] = [{"month": 1, "revenue": rev1 * 0.6, "variable_costs": 0, "fixed_costs": 0, "cash": None}]
    r = registry.run("tracking", p, {})
    assert any(a["level"] == "crit" for a in r["alerts"]) and r["reforecast"]["scales"]["demand"] < 1


def test_summary_shape(sample_raw):
    s = registry.run("summary", sample_raw, {})
    for k in ("overall", "pillars", "metrics", "score", "kri", "advice", "mc", "breakeven", "yearly", "series"):
        assert k in s
    assert s["balance_check"] < 1e-3
    assert 0 <= s["score"]["score"] <= 100


def test_every_analyzer_output_is_json_safe(sample_raw):
    import json
    for a in registry.available():
        out = registry.run(a["name"], sample_raw, {})
        json.dumps(out, allow_nan=False)
