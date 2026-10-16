"""أدوات القرار: التسعير، مزيج المنتجات (برمجة خطية)، تقييم الاستثمار (NPV/IRR)."""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq, linprog

from ..registry import analyzer


# ================================================================== التسعير
@analyzer("pricing", title="التسعير الذكي")
def pricing(ctx, params):
    p = ctx.project
    fc = ctx.forecast()
    a = fc.a
    margin = float(params.get("margin", 25)) / 100.0
    buffer_ = float(params.get("buffer", 10)) / 100.0
    margin = min(0.9, max(0.0, margin))

    n = min(12, fc.T)
    fixed_pool = float((a["payroll"][0, :n] + a["fixed"][0, :n] + a["depreciation"][0, :n] + a["interest"][0, :n]).sum()) / n
    revs = {pr["id"]: float(fc.meta["by_product"][pr["id"]]["revenue"][0, :n].sum()) for pr in p["products"]}
    tot = sum(revs.values()) or 1.0

    products = []
    for pr in p["products"]:
        units_m = float(fc.meta["by_product"][pr["id"]]["units"][0, :n].sum()) / n
        share = revs[pr["id"]] / tot
        alloc = fixed_pool * share
        per_unit_fixed = alloc / units_m if units_m > 0 else 0.0
        c = pr["unit_cost"]
        floor = c + per_unit_fixed
        rec = (c * (1 + buffer_) + per_unit_fixed) / (1 - margin)
        e = pr["elasticity"]
        p0, q0 = pr["price"], max(units_m, 0.0)
        # السعر الأمثل لمرونة ثابتة
        opt = None
        if e < -1 and c > 0:
            opt = c * e / (1 + e)
        lo_p, hi_p = (p0 * 0.6, p0 * 1.6) if p0 > 0 else (0, 0)
        curve = []
        if p0 > 0:
            for i in range(25):
                x = lo_p + (hi_p - lo_p) * i / 24
                q = q0 * (x / p0) ** e
                curve.append({"price": x, "units": q, "contribution": (x - c) * q})
        best = max(curve, key=lambda r: r["contribution"]) if curve else None
        level = "crit" if p0 < floor else "warn" if p0 < rec * 0.95 else "safe"
        products.append({
            "id": pr["id"], "name": pr["name"], "price": p0, "unit_cost": c, "unit_margin": p0 - c,
            "floor": floor, "recommended": rec, "elastic_optimum": opt, "curve": curve,
            "best_on_curve": best, "elasticity": e, "level": level, "revenue_share": share,
            "fixed_alloc_per_unit": per_unit_fixed,
        })
    return {"margin": margin * 100, "buffer": buffer_ * 100, "fixed_pool_monthly": fixed_pool, "products": products}


# ================================================================== مزيج المنتجات
@analyzer("optimizer", title="مزيج المنتجات الأمثل")
def optimizer(ctx, params):
    p = ctx.project
    prods = [pr for pr in p["products"] if pr["price"] > 0]
    if not prods:
        return {"feasible": False, "message": "أضف منتجاً واحداً على الأقل."}
    cap_total = p["capacity"]["total"]
    budget = p["capacity"]["budget"]
    n = len(prods)
    contrib = np.array([pr["price"] - pr["unit_cost"] for pr in prods])
    cost = np.array([pr["unit_cost"] for pr in prods])
    cap = np.array([pr["capacity_per_unit"] for pr in prods])
    cur = np.array([pr["units"] for pr in prods])

    A, b, names = [], [], []
    if cap_total > 0 and cap.sum() > 0:
        A.append(cap); b.append(cap_total); names.append(f"الطاقة المتاحة ({p['capacity']['unit_label']})")
    if budget > 0:
        A.append(cost); b.append(budget); names.append("ميزانية التكاليف المتغيرة")
    bounds, assumed = [], False
    for pr, c0 in zip(prods, cur):
        if pr["max_units"] > 0:
            bounds.append((0, pr["max_units"]))
        elif A:
            bounds.append((0, None))
        else:
            bounds.append((0, max(c0 * 3, 1.0)))
            assumed = True
    if not A and all(pr["max_units"] <= 0 for pr in prods):
        assumed = True
    res = linprog(-contrib, A_ub=np.array(A) if A else None, b_ub=np.array(b) if b else None,
                  bounds=bounds, method="highs")
    if res.status != 0:
        return {"feasible": False, "message": "تعذّر حل المسألة. حدّد سقفاً للطلب أو طاقة متاحة لكل منتج."}
    x = res.x
    shadow = []
    if A and hasattr(res, "ineqlin"):
        for nm, mg in zip(names, res.ineqlin.marginals):
            shadow.append({"constraint": nm, "value_per_unit": float(-mg)})
    rows = []
    for pr, xi, c0, cm in zip(prods, x, cur, contrib):
        rows.append({"id": pr["id"], "name": pr["name"], "current": float(c0), "optimal": float(xi),
                     "unit_contribution": float(cm), "max_units": pr["max_units"]})
    cur_obj = float((contrib * cur).sum())
    opt_obj = float((contrib * x).sum())
    # قيود الاستخدام الحالي
    usage = []
    if cap_total > 0 and cap.sum() > 0:
        usage.append({"name": names[0], "current": float((cap * cur).sum()), "optimal": float((cap * x).sum()), "limit": cap_total})
    if budget > 0:
        usage.append({"name": "ميزانية التكاليف المتغيرة", "current": float((cost * cur).sum()), "optimal": float((cost * x).sum()), "limit": budget})
    return {
        "feasible": True, "assumed_bounds": assumed, "rows": rows,
        "current_contribution": cur_obj, "optimal_contribution": opt_obj,
        "gain": opt_obj - cur_obj, "gain_pct": (opt_obj - cur_obj) / cur_obj if cur_obj > 0 else None,
        "shadow_prices": shadow, "usage": usage,
    }


# ================================================================== الاستثمار
def npv(rate_m: float, flows: np.ndarray) -> float:
    t = np.arange(len(flows))
    return float((flows / (1 + rate_m) ** t).sum())


def irr(flows: np.ndarray) -> float | None:
    flows = np.asarray(flows, dtype=float)
    if not (np.any(flows > 0) and np.any(flows < 0)):
        return None
    f = lambda r: float((flows / (1 + r) ** np.arange(len(flows))).sum())  # noqa: E731
    try:
        return brentq(f, -0.99, 10.0, maxiter=200)
    except ValueError:
        return None


def payback(flows: np.ndarray, rate_m: float = 0.0) -> int | None:
    disc = flows / (1 + rate_m) ** np.arange(len(flows))
    cum = np.cumsum(disc)
    neg = np.where(cum < 0)[0]
    if not len(neg):
        return 0
    after = np.where(cum[neg[0]:] >= 0)[0]
    return int(neg[0] + after[0]) if len(after) else None


@analyzer("investment", title="جدوى الاستثمار")
def investment(ctx, params):
    rate = float(params.get("rate", ctx.project["valuation"]["discount_rate"])) / 100.0
    rate_m = (1 + rate) ** (1 / 12) - 1
    manual = params.get("flows")
    if manual:  # حاسبة مستقلة: استثمار أولي + تدفقات سنوية
        outlay = float(params.get("outlay", 0))
        flows = np.array([-abs(outlay)] + [float(x) for x in manual], dtype=float)
        r = irr(flows)
        return {
            "mode": "manual", "rate": rate * 100,
            "npv": npv(rate, flows), "irr": None if r is None else r * 100,
            "payback_years": payback(flows), "discounted_payback_years": payback(flows, rate),
            "profitability_index": (npv(rate, flows) + abs(outlay)) / abs(outlay) if outlay else None,
            "flows": flows.tolist(), "unit": "سنة",
        }
    fc = ctx.forecast()
    a = fc.a
    fcff = (a["cfo"][0] + a["interest"][0] + a["cfi"][0])
    g = ctx.project["valuation"]["terminal_growth"] / 100.0
    tv = 0.0
    if rate > g:
        tv = float(fcff[-12:].sum()) * (1 + g) / (rate - g)
    flows = fcff.copy()
    npv_ops = npv(rate_m, flows)
    npv_tv = tv / (1 + rate_m) ** (len(flows) - 1) if tv > 0 else 0.0
    cum = np.cumsum(fcff)
    trough = float(cum.min())
    flows_with_tv = flows.copy()
    flows_with_tv[-1] += tv
    r = irr(flows_with_tv)
    r_annual = None if r is None else ((1 + r) ** 12 - 1) * 100
    pb = payback(flows)
    return {
        "mode": "project", "rate": rate * 100, "terminal_growth": g * 100,
        "npv_operations": npv_ops, "terminal_value": tv, "pv_terminal_value": npv_tv, "npv": npv_ops + npv_tv,
        "irr": r_annual, "payback_months": pb, "discounted_payback_months": payback(flows, rate_m),
        "peak_funding_need": max(0.0, -trough), "trough_month": int(cum.argmin()) + 1,
        "cumulative_fcff": cum.tolist(), "fcff_by_year": [float(fcff[i:i + 12].sum()) for i in range(0, fc.T, 12)],
        "note": "التدفق الحر = التدفق التشغيلي + الفوائد المدفوعة − الاستثمارات (قبل التمويل).",
    }
