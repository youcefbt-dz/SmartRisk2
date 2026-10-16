"""تحليل الحساسية (Tornado) والصدمات العكسية وتحليل السيناريوهات."""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from ..engine.forecast import Shocks
from ..registry import analyzer

METRICS = {
    "net_income_y1": ("الربح الصافي للسنة الأولى", lambda fc: float(fc.a["net_income"][0, :12].sum())),
    "min_cash": ("أدنى رصيد نقدي", lambda fc: float(fc.a["cash"][0].min())),
    "final_cash": ("الرصيد النقدي النهائي", lambda fc: float(fc.a["cash"][0, -1])),
}


def _scale_products(p, key, f):
    for pr in p["products"]:
        pr[key] *= f


def _driver_price(p, x): _scale_products(p, "price", 1 + x)
def _driver_demand(p, x): _scale_products(p, "units", 1 + x)
def _driver_unit_cost(p, x): _scale_products(p, "unit_cost", 1 + x)
def _driver_fixed(p, x):
    for f in p["fixed_costs"]:
        f["amount"] *= 1 + x
def _driver_payroll(p, x):
    for s in p["staff"]:
        s["gross"] *= 1 + x
def _driver_customer_days(p, x):
    d = p["working_capital"]["customer_days"]
    p["working_capital"]["customer_days"] = max(0.0, d + x * max(d, 15.0))
def _driver_growth(p, x):
    for pr in p["products"]:
        pr["growth"] += x * 10.0  # ±10% ← ±1 نقطة مئوية شهرياً
def _driver_rate(p, x):
    for ln in p["loans"]:
        ln["rate"] *= 1 + x
def _driver_inflation(p, x):
    p["macro"]["cost_inflation"] += x * 20.0


DRIVERS = [
    ("price", "سعر البيع", _driver_price),
    ("demand", "حجم المبيعات", _driver_demand),
    ("unit_cost", "تكلفة الوحدة", _driver_unit_cost),
    ("fixed", "التكاليف الثابتة", _driver_fixed),
    ("payroll", "الأجور", _driver_payroll),
    ("customer_days", "مدة تحصيل الزبائن", _driver_customer_days),
    ("growth", "نمو المبيعات الشهري (±1 نقطة)", _driver_growth),
    ("rate", "سعر فائدة القروض", _driver_rate),
    ("inflation", "تضخم التكاليف (±2 نقطة)", _driver_inflation),
]


def apply_driver(p: dict, key: str, x: float) -> dict:
    q = deepcopy(p)
    for k, _, fn in DRIVERS:
        if k == key:
            fn(q, x)
            break
    return q


@analyzer("sensitivity", title="تحليل الحساسية")
def sensitivity(ctx, params):
    pct = float(min(50, max(1, params.get("pct", 10)))) / 100.0
    base_fc = ctx.forecast()
    out = {"pct": pct * 100, "metrics": {}, "labels": {k: v[0] for k, v in METRICS.items()}}
    base = {m: fn(base_fc) for m, (_, fn) in METRICS.items()}
    rows = {m: [] for m in METRICS}
    for key, label, _ in DRIVERS:
        # تجاهل المحرّكات غير ذات الصلة
        if key == "rate" and not ctx.project["loans"]:
            continue
        lo = ctx.forecast(apply_driver(ctx.project, key, -pct))
        hi = ctx.forecast(apply_driver(ctx.project, key, +pct))
        for m, (_, fn) in METRICS.items():
            vlo, vhi = fn(lo), fn(hi)
            rows[m].append({"key": key, "label": label, "low": vlo, "high": vhi, "base": base[m],
                            "swing": abs(vhi - vlo)})
    for m in METRICS:
        out["metrics"][m] = {"base": base[m], "rows": sorted(rows[m], key=lambda r: -r["swing"])}
    return out


# ----------------------------------------------------------------- الصدمات العكسية
def _bisect(f, lo: float, hi: float, iters: int = 40) -> float:
    """f(lo) ≥ 0 و f(hi) < 0 (أو العكس مع اعتبار الإشارة)؛ يعيد نقطة العبور."""
    flo = f(lo)
    for _ in range(iters):
        mid = (lo + hi) / 2
        if (f(mid) >= 0) == (flo >= 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@analyzer("reverse_stress", title="اختبار الصدمات العكسي")
def reverse_stress(ctx, params):
    """«ما الذي يجب أن يحدث ليفشل مشروعي؟»: يبحث عن حجم الصدمة التي تُنفد السيولة."""
    base_min = float(ctx.forecast().a["cash"][0].min())
    base_ni = float(ctx.forecast().a["net_income"][0, :12].sum())

    def min_cash(**kw) -> float:
        fc = ctx.forecast(None, Shocks.scalar(**kw))
        return float(fc.a["cash"][0].min())

    def ni_y1(**kw) -> float:
        fc = ctx.forecast(None, Shocks.scalar(**kw))
        return float(fc.a["net_income"][0, :12].sum())

    items = []

    def add(key, label, unit, fn, lo, hi, kw, to_display, phrase, metric="cash"):
        """lo = القيمة المحايدة، hi = القيمة القصوى المختبَرة (اتجاه الصدمة)."""
        f = (lambda x: fn(**{kw: x})) if metric == "cash" else (lambda x: fn(**{kw: x}))
        if f(lo) < 0:
            items.append({"key": key, "label": label, "status": "already", "metric": metric,
                          "statement": "الوضع الحالي يعاني عجزاً بالفعل قبل أي صدمة." if metric == "cash"
                          else "المشروع خاسر بالفعل في السنة الأولى قبل أي صدمة."})
            return
        if f(hi) >= 0:
            items.append({"key": key, "label": label, "status": "never", "metric": metric,
                          "statement": f"لا يفشل المشروع حتى عند {phrase(to_display(hi))}."})
            return
        x = _bisect(f, lo, hi)
        items.append({"key": key, "label": label, "status": "found", "metric": metric,
                      "threshold": to_display(x),
                      "statement": f"يفشل المشروع عند {phrase(to_display(x))}."})

    # السيولة
    add("demand", "هبوط المبيعات", "%", min_cash, 1.0, 0.0, "demand",
        lambda x: (1 - x) * 100, lambda v: f"هبوط المبيعات بنسبة {v:.0f}%")
    add("price", "هبوط السعر", "%", min_cash, 1.0, 0.0, "price",
        lambda x: (1 - x) * 100, lambda v: f"هبوط السعر بنسبة {v:.0f}%")
    add("cost", "ارتفاع تكلفة الوحدة", "%", min_cash, 1.0, 5.0, "cost",
        lambda x: (x - 1) * 100, lambda v: f"ارتفاع تكلفة الوحدة بنسبة {v:.0f}%")
    add("fixed", "ارتفاع التكاليف الثابتة", "%", min_cash, 1.0, 10.0, "fixed",
        lambda x: (x - 1) * 100, lambda v: f"ارتفاع التكاليف الثابتة بنسبة {v:.0f}%")
    add("collection", "تأخر تحصيل الزبائن", "يوم", min_cash, 0.0, 240.0, "collect_add",
        lambda x: x, lambda v: f"تأخر التحصيل {v:.0f} يوماً إضافياً")
    # الربحية
    add("ni_demand", "هبوط المبيعات حتى الخسارة السنوية", "%", ni_y1, 1.0, 0.0, "demand",
        lambda x: (1 - x) * 100, lambda v: f"هبوط المبيعات بنسبة {v:.0f}%", metric="profit")

    # صدمة مركّبة: λ × (−30% طلب، +20% تكلفة، +30 يوم تحصيل)
    def combo(lam):
        return min_cash(demand=1 - 0.30 * lam, cost=1 + 0.20 * lam, collect_add=30 * lam)
    combined = None
    if combo(0.0) < 0:
        combined = {"status": "already", "statement": "الوضع الحالي يعاني عجزاً قبل أي صدمة."}
    elif combo(1.0) >= 0:
        combined = {"status": "never", "statement": "يصمد المشروع أمام صدمة مركّبة (مبيعات −30% وتكلفة +20% وتحصيل +30 يوماً)."}
    else:
        lam = _bisect(combo, 0.0, 1.0)
        combined = {"status": "found", "lambda": lam,
                    "statement": f"يفشل المشروع عند {lam * 100:.0f}% من صدمة مركّبة (مبيعات −30%، تكلفة +20%، تحصيل +30 يوماً)."}
    return {"base_min_cash": base_min, "base_net_income_y1": base_ni, "items": items, "combined": combined}


# ----------------------------------------------------------------- السيناريوهات
DEFAULT_SCENARIOS = [
    {"name": "متشائم", "demand_pct": -20, "price_pct": -5, "cost_pct": 15, "fixed_pct": 5, "collect_days": 15, "color": "crit"},
    {"name": "أساسي", "demand_pct": 0, "price_pct": 0, "cost_pct": 0, "fixed_pct": 0, "collect_days": 0, "color": "base"},
    {"name": "متفائل", "demand_pct": 15, "price_pct": 3, "cost_pct": -5, "fixed_pct": 0, "collect_days": -5, "color": "safe"},
]


@analyzer("scenarios", title="مقارنة السيناريوهات")
def scenarios(ctx, params):
    scs = params.get("scenarios") or DEFAULT_SCENARIOS
    out = []
    for sc in scs[:6]:
        sh = Shocks.scalar(
            demand=1 + float(sc.get("demand_pct", 0)) / 100, price=1 + float(sc.get("price_pct", 0)) / 100,
            cost=1 + float(sc.get("cost_pct", 0)) / 100, fixed=1 + float(sc.get("fixed_pct", 0)) / 100,
            collect_add=float(sc.get("collect_days", 0)),
        )
        fc = ctx.forecast(None, sh)
        cash = fc.a["cash"][0]
        neg = np.where(cash < 0)[0]
        out.append({
            "name": str(sc.get("name", "سيناريو"))[:30], "color": sc.get("color", "base"),
            "params": {k: sc.get(k, 0) for k in ("demand_pct", "price_pct", "cost_pct", "fixed_pct", "collect_days")},
            "cash": cash.tolist(),
            "revenue_by_year": fc.annual("revenue"), "net_income_by_year": fc.annual("net_income"),
            "min_cash": float(cash.min()), "final_cash": float(cash[-1]),
            "cash_out_month": int(neg[0]) + 1 if len(neg) else None,
        })
    return {"scenarios": out, "months": list(range(1, ctx.project["horizon"] + 1))}
