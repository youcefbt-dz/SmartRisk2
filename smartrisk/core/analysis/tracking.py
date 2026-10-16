"""المتابعة: مقارنة الأرقام الفعلية بالتوقع، تنبيهات الانحراف، وإعادة التوقع."""
from __future__ import annotations

import numpy as np

from ..engine.forecast import Shocks
from ..registry import analyzer

REV_WARN, REV_CRIT = 0.10, 0.20     # هبوط الإيراد عن التوقع
COST_WARN, COST_CRIT = 0.10, 0.20   # تجاوز التكاليف


def _var(actual: float, plan: float) -> float | None:
    return (actual - plan) / plan if plan > 1e-9 else None


@analyzer("tracking", title="المتابعة الشهرية")
def tracking(ctx, params):
    p = ctx.project
    acts = p.get("actuals") or []
    fc = ctx.forecast()
    a = fc.a
    rows, alerts = [], []
    streak_rev = 0
    for x in acts:
        k = x["month"] - 1
        if k >= fc.T:
            continue
        f_rev = float(a["revenue"][0, k]); f_var = float(a["cogs"][0, k])
        f_fix = float(a["payroll"][0, k] + a["fixed"][0, k] + a["one_off"][0, k]); f_cash = float(a["cash"][0, k])
        v_rev = _var(x["revenue"], f_rev)
        v_var = _var(x["variable_costs"], f_var)
        v_fix = _var(x["fixed_costs"], f_fix)
        v_cash = None if x["cash"] is None else _var(x["cash"], f_cash) if f_cash > 0 else None
        rows.append({
            "month": x["month"],
            "revenue": {"plan": f_rev, "actual": x["revenue"], "var": v_rev},
            "variable_costs": {"plan": f_var, "actual": x["variable_costs"], "var": v_var},
            "fixed_costs": {"plan": f_fix, "actual": x["fixed_costs"], "var": v_fix},
            "cash": {"plan": f_cash, "actual": x["cash"], "var": v_cash},
            "profit": {"plan": f_rev - f_var - f_fix, "actual": x["revenue"] - x["variable_costs"] - x["fixed_costs"]},
        })
        streak_rev = streak_rev + 1 if (v_rev is not None and v_rev < -REV_WARN) else 0
        m = x["month"]
        if v_rev is not None and v_rev < -REV_CRIT:
            alerts.append({"month": m, "level": "crit", "title": "الإيراد أقل من التوقع بكثير",
                           "text": f"الشهر {m}: الإيراد الفعلي أقل من التوقع بنسبة {abs(v_rev) * 100:.0f}%."})
        elif v_rev is not None and v_rev < -REV_WARN:
            alerts.append({"month": m, "level": "warn", "title": "الإيراد دون التوقع",
                           "text": f"الشهر {m}: الإيراد أقل من التوقع بنسبة {abs(v_rev) * 100:.0f}%."})
        if streak_rev >= 2:
            alerts.append({"month": m, "level": "crit", "title": "انحراف متكرر في الإيراد",
                           "text": f"الإيراد دون التوقع منذ {streak_rev} أشهر متتالية؛ راجع فرضيات المبيعات فوراً."})
        for key, v, name in (("variable_costs", v_var, "التكاليف المتغيرة"), ("fixed_costs", v_fix, "التكاليف الثابتة")):
            if v is not None and v > COST_CRIT:
                alerts.append({"month": m, "level": "crit", "title": f"{name} تجاوزت التوقع",
                               "text": f"الشهر {m}: {name} أعلى من التوقع بنسبة {v * 100:.0f}%."})
            elif v is not None and v > COST_WARN:
                alerts.append({"month": m, "level": "warn", "title": f"{name} فوق التوقع",
                               "text": f"الشهر {m}: {name} أعلى من التوقع بنسبة {v * 100:.0f}%."})
        if x["cash"] is not None and x["cash"] < 0:
            alerts.append({"month": m, "level": "crit", "title": "رصيد نقدي سالب",
                           "text": f"الشهر {m}: الرصيد الفعلي سالب."})
        elif x["cash"] is not None and x["cash"] < f_cash * 0.5 and f_cash > 0:
            alerts.append({"month": m, "level": "warn", "title": "السيولة أقل من نصف المتوقع",
                           "text": f"الشهر {m}: الرصيد الفعلي أقل من نصف المتوقع."})
    out = {"rows": rows, "alerts": alerts, "months_tracked": len(rows), "reforecast": None}
    if rows:
        out["reforecast"] = _reforecast(ctx, rows)
    return out


def _reforecast(ctx, rows: list[dict]) -> dict | None:
    """يعدّل الطلب والتكاليف المستقبلية بحسب متوسط آخر 3 أشهر فعلية ويثبّت الرصيد على آخر رصيد فعلي."""
    p = ctx.project
    T = p["horizon"]
    last = rows[-1]["month"]
    tail = rows[-3:]
    pr = sum(r["revenue"]["plan"] for r in tail)
    ar = sum(r["revenue"]["actual"] for r in tail)
    pv = sum(r["variable_costs"]["plan"] for r in tail)
    av = sum(r["variable_costs"]["actual"] for r in tail)
    pf = sum(r["fixed_costs"]["plan"] for r in tail)
    af = sum(r["fixed_costs"]["actual"] for r in tail)
    if pr <= 0:
        return None
    demand = float(np.clip(ar / pr, 0.2, 3.0))
    unit_cost = float(np.clip((av / pv) / demand, 0.5, 2.0)) if pv > 0 else 1.0
    fixed = float(np.clip(af / pf, 0.5, 2.0)) if pf > 0 else 1.0
    dm = np.ones((1, T)); cm = np.ones((1, T)); fm = np.ones((1, T))
    dm[:, last:] = demand; cm[:, last:] = unit_cost; fm[:, last:] = fixed
    fc = ctx.forecast(None, Shocks(n=1, demand=dm, cost=cm, fixed=fm))
    cash = fc.a["cash"][0].copy()
    anchor = None
    for r in reversed(rows):
        if r["cash"]["actual"] is not None:
            anchor = r
            break
    if anchor is not None:
        k = anchor["month"] - 1
        cash = cash + (anchor["cash"]["actual"] - cash[k])
    neg = np.where(cash[last:] < 0)[0]
    base_cash = ctx.forecast().a["cash"][0]
    return {
        "from_month": last + 1,
        "scales": {"demand": demand, "unit_cost": unit_cost, "fixed": fixed},
        "months": list(range(last + 1, T + 1)),
        "cash": cash[last:].tolist(),
        "base_cash": base_cash[last:].tolist(),
        "cash_out_month": int(neg[0]) + last + 1 if len(neg) else None,
        "min_cash": float(cash[last:].min()) if len(cash[last:]) else None,
    }
