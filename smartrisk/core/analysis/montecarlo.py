"""محاكاة مونت كارلو للسيولة: آلاف السيناريوهات العشوائية للطلب والتكلفة والتحصيل."""
from __future__ import annotations

import numpy as np

from ..engine.forecast import Shocks
from ..registry import analyzer

DEFAULT_N = 2000
MAX_N = 10000
AR_RHO = 0.5


def build_shocks(p: dict, n: int, seed: int | None, T: int | None = None) -> Shocks:
    """يبني صدمات عشوائية (مولّد ثابت البذرة لقابلية إعادة الإنتاج ولمقارنة الخيارات بنفس الأرقام)."""
    T = T or p["horizon"]
    rng = np.random.default_rng(seed)
    rk = p["risk"]
    u = rk["uncertainty"]
    dv, cv, pv = rk["demand_vol"] / 100 * u, rk["cost_vol"] / 100 * u, rk["price_vol"] / 100 * u

    def ar1(sigma: float) -> np.ndarray:
        s_innov = sigma * np.sqrt(1 - AR_RHO ** 2)
        x = np.zeros((n, T))
        x[:, 0] = rng.normal(0, sigma, n)
        for t in range(1, T):
            x[:, t] = AR_RHO * x[:, t - 1] + rng.normal(0, s_innov, n)
        return x

    d_level = rng.normal(0, dv, (n, 1))
    d_noise = ar1(dv * 0.5)
    demand = np.exp(d_level + d_noise - 0.5 * (dv ** 2 + (dv * 0.5) ** 2))

    c_level = rng.normal(0, cv, (n, 1))
    c_noise = ar1(cv * 0.5)
    cost = np.exp(c_level + c_noise - 0.5 * (cv ** 2 + (cv * 0.5) ** 2))

    price = np.exp(rng.normal(0, pv, (n, T)) - 0.5 * pv ** 2)
    wc = p["working_capital"]
    collect_add = rng.normal(0, rk["collection_vol_days"] * u, n)
    collect_add = np.maximum(collect_add, -wc["customer_days"])
    return Shocks(n=n, demand=demand, price=price, cost=cost, collect_add=collect_add)


def get_mc(ctx, n: int = DEFAULT_N, seed: int | None = 42, project: dict | None = None, regime: str | None = None) -> dict:
    """يشغّل المحاكاة (مع تخزين النتيجة داخل السياق). يعيد قاموساً بالصفائف الخام والملخصات."""
    key = f"mc:{n}:{seed}" if project is None else None

    def run():
        proj = project or ctx.project
        sh = build_shocks(ctx.project, n, seed)
        fc = ctx.forecast(proj, sh)
        a = fc.a
        cash = a["cash"]
        min_cash = cash.min(axis=1)
        ever_neg = np.minimum.accumulate(cash, axis=1) < 0
        ni_y1 = a["net_income"][:, :12].sum(axis=1)
        T = fc.T
        pct = lambda arr, q: np.percentile(arr, q, axis=0)  # noqa: E731
        bands = {f"p{q}": pct(cash, q) for q in (5, 25, 50, 75, 95)}
        h = min(12, T)
        res = {
            "n": n, "seed": seed, "T": T,
            "cash": cash, "min_cash": min_cash,
            "bands": bands,
            "p_ruin_by_month": ever_neg.mean(axis=0),
            "p_ruin_6": float(ever_neg[:, min(5, T - 1)].mean()),
            "p_ruin_12": float(ever_neg[:, h - 1].mean()),
            "p_ruin_horizon": float(ever_neg[:, -1].mean()),
            "ni_y1": ni_y1,
            "final_cash": cash[:, -1],
        }
        return res

    if key:
        return ctx.memo(key, run)
    return run()


def summarize(res: dict, bins: int = 24) -> dict:
    fin = res["final_cash"]
    mn = res["min_cash"]
    ni = res["ni_y1"]

    def hist(x):
        counts, edges = np.histogram(x, bins=bins)
        return {"edges": edges.tolist(), "counts": counts.tolist()}

    p5 = float(np.percentile(mn, 5))
    p1 = float(np.percentile(mn, 1))
    worst_k = max(1, int(len(fin) * 0.05))
    es = float(np.sort(fin)[:worst_k].mean())
    return {
        "n": res["n"], "seed": res["seed"],
        "months": list(range(1, res["T"] + 1)),
        "bands": {k: v.tolist() for k, v in res["bands"].items()},
        "p_ruin_by_month": res["p_ruin_by_month"].tolist(),
        "p_ruin_6": res["p_ruin_6"], "p_ruin_12": res["p_ruin_12"], "p_ruin_horizon": res["p_ruin_horizon"],
        "p_survive_12": 1 - res["p_ruin_12"],
        "cash_at_risk_95": max(0.0, -p5), "cash_at_risk_99": max(0.0, -p1),
        "expected_min_cash": float(mn.mean()), "median_final_cash": float(np.median(fin)),
        "mean_final_cash": float(fin.mean()), "expected_shortfall_final": es,
        "final_cash_hist": hist(fin), "min_cash_hist": hist(mn),
        "ni_y1": {"p5": float(np.percentile(ni, 5)), "p50": float(np.percentile(ni, 50)),
                  "p95": float(np.percentile(ni, 95)), "p_loss": float((ni < 0).mean())},
    }


@analyzer("montecarlo", title="محاكاة مونت كارلو")
def montecarlo(ctx, params):
    n = int(min(MAX_N, max(200, params.get("n", DEFAULT_N))))
    seed = params.get("seed", 42)
    seed = None if seed in (None, "") else int(seed)
    res = get_mc(ctx, n, seed)
    out = summarize(res)
    out["baseline_cash"] = ctx.forecast().a["cash"][0].tolist()
    out["uncertainty"] = ctx.project["risk"]
    return out
