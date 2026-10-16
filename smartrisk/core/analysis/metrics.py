"""المؤشرات الأساسية المشتقة من التوقع الحتمي، وهي مصدر مشترك للمخاطر والنصائح والتقارير."""
from __future__ import annotations

import numpy as np

from ..registry import analyzer
from ..util import clamp


def _y1(arr: np.ndarray) -> float:
    return float(arr[:12].sum())


def breakeven_block(ctx) -> dict:
    p = ctx.project
    fc = ctx.forecast()
    a = fc.a
    rev1 = _y1(a["revenue"][0])
    cogs1 = _y1(a["cogs"][0])
    cmr = (rev1 - cogs1) / rev1 if rev1 > 0 else 0.0
    n = min(12, fc.T)
    op_fixed = (_y1(a["payroll"][0]) + _y1(a["fixed"][0]) + _y1(a["depreciation"][0])) / n
    interest = _y1(a["interest"][0]) / n
    repay = _y1(a["loan_repay"][0]) / n
    be_op = op_fixed / cmr if cmr > 0 else None
    be_total = (op_fixed + interest) / cmr if cmr > 0 else None
    be_cash = (op_fixed - _y1(a["depreciation"][0]) / n + interest + repay) / cmr if cmr > 0 else None
    avg_rev = rev1 / n
    mos = None
    if be_total is not None and avg_rev > 0:
        mos = (avg_rev - be_total) / avg_rev
    # حدود المنحنى
    curve = None
    if be_total:
        top = max(avg_rev, be_total) * 1.8
        xs = [top * i / 20 for i in range(21)]
        curve = {
            "revenue": xs,
            "total_cost": [op_fixed + interest + x * (1 - cmr) for x in xs],
        }
    # تعادل كل منتج عند المزيج الحالي
    per_product = []
    if be_total:
        tot_rev = {pr["id"]: _y1(fc.meta["by_product"][pr["id"]]["revenue"][0]) for pr in p["products"]}
        s = sum(tot_rev.values()) or 1.0
        for pr in p["products"]:
            share = tot_rev[pr["id"]] / s
            units = share * be_total / pr["price"] if pr["price"] > 0 else None
            per_product.append({"id": pr["id"], "name": pr["name"], "share": share, "units": units,
                                "current_units": pr["units"]})
    return {
        "contribution_margin_ratio": cmr, "operating_fixed_monthly": op_fixed,
        "breakeven_operating": be_op, "breakeven_total": be_total, "breakeven_cash": be_cash,
        "avg_monthly_revenue": avg_rev, "margin_of_safety": mos, "curve": curve, "per_product": per_product,
    }


def zscore(ctx, month_index: int | None = None) -> dict | None:
    """Altman Z″ (شركات غير صناعية / أسواق ناشئة) على نهاية السنة الأولى."""
    fc = ctx.forecast()
    a = fc.a
    k = (month_index if month_index is not None else min(11, fc.T - 1))
    ta = float(a["total_assets"][0, k])
    if ta <= 0:
        return None
    ca = float(a["cash"][0, k] + a["receivables"][0, k] + a["inventory"][0, k])
    nxt = a["loan_repay"][0, k + 1:k + 13]
    cur_loans = float(nxt.sum())
    cl = float(a["payables"][0, k]) + max(0.0, float(a["vat_liab"][0, k])) + float(a["tax_payable"][0, k]) + cur_loans
    wc = ca - cl
    re = float(a["net_income"][0, :k + 1].sum()) + 0.0
    ebit = float(a["ebit"][0, max(0, k - 11):k + 1].sum())
    tl = float(a["total_liabilities"][0, k])
    eq = float(a["equity"][0, k])
    x1, x2, x3 = wc / ta, re / ta, ebit / ta
    x4 = clamp(eq / tl, -10, 10) if tl > 1e-6 else 10.0
    z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    zone = "safe" if z > 2.6 else "warn" if z >= 1.1 else "crit"
    return {"z": z, "zone": zone, "x1": x1, "x2": x2, "x3": x3, "x4": x4, "month": k + 1}


def compute_metrics(ctx) -> dict:
    p = ctx.project
    fc = ctx.forecast()
    a = fc.a
    T = fc.T
    rev1 = _y1(a["revenue"][0])
    gp1 = _y1(a["gross_profit"][0])
    ni1 = _y1(a["net_income"][0])
    ebitda1 = _y1(a["ebitda"][0])
    tax1 = _y1(a["tax"][0])
    ds1 = _y1(a["interest"][0]) + _y1(a["loan_repay"][0])
    dscr = (ebitda1 - tax1) / ds1 if ds1 > 1e-6 else None

    obl = min(3, T)
    monthly_obl = float((a["payroll"][0, :obl] + a["fixed"][0, :obl] + a["interest"][0, :obl] + a["loan_repay"][0, :obl]).mean())
    runway = (p["start_cash"] / monthly_obl) if monthly_obl > 1e-6 else 99.0
    runway = min(99.0, runway)

    cash = a["cash"][0]
    neg = np.where(cash < 0)[0]
    be = breakeven_block(ctx)
    z = zscore(ctx)
    wc = p["working_capital"]

    shares = {}
    for pr in p["products"]:
        shares[pr["name"]] = _y1(fc.meta["by_product"][pr["id"]]["revenue"][0])
    tot = sum(shares.values())
    top_share = max(shares.values()) / tot if tot > 0 else 0.0

    return {
        "revenue_y1": rev1,
        "revenue_by_year": fc.annual("revenue"),
        "net_income_by_year": fc.annual("net_income"),
        "gross_margin_y1": gp1 / rev1 if rev1 > 0 else 0.0,
        "net_margin_y1": ni1 / rev1 if rev1 > 0 else 0.0,
        "ebitda_y1": ebitda1,
        "net_income_y1": ni1,
        "dscr": dscr,
        "runway_months": runway,
        "min_cash": float(cash.min()),
        "min_cash_month": int(cash.argmin()) + 1,
        "cash_out_month": int(neg[0]) + 1 if len(neg) else None,
        "final_cash": float(cash[-1]),
        "customer_days": wc["customer_days"],
        "inventory_days": wc["inventory_days"],
        "supplier_days": wc["supplier_days"],
        "cash_cycle_days": wc["customer_days"] + wc["inventory_days"] - wc["supplier_days"],
        "top_product_share": top_share,
        "z_score": z["z"] if z else None,
        "z_zone": z["zone"] if z else None,
        "margin_of_safety": be["margin_of_safety"],
        "breakeven_total": be["breakeven_total"],
        "regime": fc.meta["regime"],
    }


@analyzer("breakeven", title="نقطة التعادل")
def breakeven(ctx, params):
    return breakeven_block(ctx)


@analyzer("zscore", title="مؤشر Altman Z″")
def zscore_analyzer(ctx, params):
    out = {}
    for k in (11, 23, 35):
        if k < ctx.forecast().T:
            out[f"y{(k + 1) // 12}"] = zscore(ctx, k)
    return out


@analyzer("metrics", title="المؤشرات الأساسية")
def metrics_analyzer(ctx, params):
    return ctx.metrics()
