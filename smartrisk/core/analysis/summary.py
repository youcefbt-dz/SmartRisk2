"""الحزمة الشاملة للوحة القيادة والتقرير: استدعاء واحد يجمع كل ما تحتاجه الواجهة."""
from __future__ import annotations

from ..registry import analyzer
from ..util import LEVEL_AR, level_of, worst
from . import advice as advice_mod
from . import metrics as metrics_mod
from . import scoring as scoring_mod
from .montecarlo import get_mc, summarize


def _pillars(ctx, m: dict, score: dict) -> list[dict]:
    liq = "crit" if (m["cash_out_month"] or m["p_ruin_12"] > 0.2) else "warn" if m["p_ruin_12"] > 0.05 or m["runway_months"] < 3 else "safe"
    prof = "safe" if m["revenue_y1"] <= 0 else level_of(m["net_margin_y1"], 0.08, 0.0, "higher")
    mos = m["margin_of_safety"]
    struct = "safe" if (mos is None or m["revenue_y1"] <= 0) else level_of(mos, 0.25, 0.1, "higher")
    pillars = [
        {"id": "liquidity", "title": "السيولة", "level": liq},
        {"id": "profit", "title": "الربحية", "level": prof},
        {"id": "structure", "title": "هامش الأمان", "level": struct},
        {"id": "funding", "title": "جاهزية التمويل", "level": score["level"]},
    ]
    for pl in pillars:
        pl["label"] = LEVEL_AR[pl["level"]]
    return pillars


@analyzer("summary", title="الملخص الشامل")
def summary(ctx, params):
    p = ctx.project
    fc = ctx.forecast()
    a = fc.a
    m = scoring_mod.full_metrics(ctx)
    score = scoring_mod.scoring(ctx, {})
    kri = scoring_mod.kri(ctx, {})
    adv = advice_mod.advice(ctx, {})
    mc = summarize(get_mc(ctx))
    be = metrics_mod.breakeven_block(ctx)
    pillars = _pillars(ctx, m, score)
    overall = worst([x["level"] for x in pillars])
    empty = not p["products"] or all(pr["price"] * pr["units"] <= 0 for pr in p["products"])

    yearly = []
    for y in range(int(-(-fc.T // 12))):
        sl = slice(y * 12, (y + 1) * 12)
        rev = float(a["revenue"][0, sl].sum())
        yearly.append({
            "year": y + 1, "revenue": rev,
            "gross_profit": float(a["gross_profit"][0, sl].sum()), "ebitda": float(a["ebitda"][0, sl].sum()),
            "net_income": float(a["net_income"][0, sl].sum()), "cfo": float(a["cfo"][0, sl].sum()),
            "end_cash": float(a["cash"][0, sl][-1]),
            "net_margin": float(a["net_income"][0, sl].sum() / rev) if rev > 0 else None,
        })
    return {
        "name": p["name"], "empty": empty, "overall": overall, "overall_label": LEVEL_AR[overall],
        "pillars": pillars, "metrics": m, "score": score, "kri": kri, "advice": adv, "mc": mc, "breakeven": be,
        "yearly": yearly, "regime": fc.meta["regime"], "regime_notes": fc.meta["notes"],
        "input_warnings": ctx.warnings,
        "series": {
            "months": list(range(1, fc.T + 1)),
            "revenue": a["revenue"][0].tolist(), "net_income": a["net_income"][0].tolist(),
            "cash": a["cash"][0].tolist(), "ebitda": a["ebitda"][0].tolist(),
        },
        "balance_check": float(abs(a["check"]).max()),
    }
