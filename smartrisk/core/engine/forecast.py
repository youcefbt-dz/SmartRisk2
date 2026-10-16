"""المحرك المالي الشهري: قائمة الدخل + التدفقات النقدية + الميزانية في نموذج واحد مترابط.

المحرك متّجه (vectorised) على N مساراً في آن واحد: N=1 للتوقع الحتمي، وN كبير لمحاكاة مونت كارلو.
كل الصفائف بالشكل (N, T) حيث T عدد الأشهر.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import loans as loans_mod
from . import rules as rules_mod

FLOW_KEYS = [
    "units", "revenue", "vat_out", "cogs", "gross_profit", "payroll", "fixed", "one_off", "opex",
    "ebitda", "depreciation", "ebit", "interest", "ebt", "tax", "net_income",
    "collections", "supplier_paid", "vat_paid", "tax_paid", "capex", "loan_disb", "loan_repay",
    "equity_inj", "cfo", "cfi", "cff", "net_cash_flow", "purchases",
]
STOCK_KEYS = [
    "cash", "receivables", "inventory", "fixed_assets", "total_assets",
    "payables", "vat_liab", "tax_payable", "loans", "total_liabilities", "equity",
]


@dataclass
class Shocks:
    """معاملات الصدمات: مضاعفات (N,T) وأيام إضافية (N,)."""
    n: int = 1
    demand: np.ndarray | None = None
    price: np.ndarray | None = None
    cost: np.ndarray | None = None
    fixed: np.ndarray | None = None
    collect_add: np.ndarray | None = None
    supply_add: np.ndarray | None = None

    @staticmethod
    def scalar(demand: float = 1.0, price: float = 1.0, cost: float = 1.0, fixed: float = 1.0,
               collect_add: float = 0.0, supply_add: float = 0.0) -> "Shocks":
        return Shocks(
            n=1,
            demand=np.full((1, 1), demand), price=np.full((1, 1), price),
            cost=np.full((1, 1), cost), fixed=np.full((1, 1), fixed),
            collect_add=np.array([collect_add]), supply_add=np.array([supply_add]),
        )

    def resolved(self, T: int) -> "Shocks":
        N = self.n
        def mat(a, default=1.0):
            if a is None:
                return np.full((N, T), default)
            return np.broadcast_to(a, (N, T)).astype(float)
        def vec(a):
            return np.zeros(N) if a is None else np.broadcast_to(a, (N,)).astype(float)
        return Shocks(N, mat(self.demand), mat(self.price), mat(self.cost), mat(self.fixed),
                      vec(self.collect_add), vec(self.supply_add))


@dataclass
class Forecast:
    a: dict[str, np.ndarray]
    meta: dict = field(default_factory=dict)

    @property
    def T(self) -> int:
        return self.meta["T"]

    @property
    def N(self) -> int:
        return self.meta["N"]

    def row(self, key: str, n: int = 0) -> np.ndarray:
        return self.a[key][n]

    def annual(self, key: str, n: int = 0, stock: bool = False) -> list[float]:
        """مجاميع سنوية للتدفقات أو قيمة نهاية السنة للأرصدة."""
        x = self.a[key][n]
        years = int(np.ceil(self.T / 12))
        out = []
        for y in range(years):
            seg = x[y * 12:(y + 1) * 12]
            out.append(float(seg[-1] if stock else seg.sum()))
        return out

    def to_dict(self, n: int = 0) -> dict:
        d = {k: [float(v) for v in self.a[k][n]] for k in self.a if self.a[k].ndim == 2}
        d["products"] = {pid: {k: [float(v) for v in arr[n]] for k, arr in vals.items()}
                         for pid, vals in self.meta.get("by_product", {}).items()}
        return d


# ---------------------------------------------------------------- helpers
def lag_series(x: np.ndarray, lag_months: np.ndarray) -> np.ndarray:
    """يزيح كل مسار n بمقدار lag_months[n] (كسري) مع استيفاء خطي؛ ما قبل البداية = 0."""
    N, T = x.shape
    t = np.arange(T)[None, :]
    idx = t - lag_months[:, None]
    i0 = np.floor(idx).astype(int)
    w = idx - i0
    rows = np.arange(N)[:, None]

    def gather(i):
        ok = (i >= 0) & (i < T)
        return np.where(ok, x[rows, np.clip(i, 0, T - 1)], 0.0)

    return (1.0 - w) * gather(i0) + w * gather(i0 + 1)


def seasonal_vector(p: dict, T: int) -> np.ndarray:
    s = np.array(p["seasonality"], dtype=float)
    s = s / s.mean()
    cal = (p["start_month"] - 1 + np.arange(T)) % 12
    return s[cal]


def resolve_regime(p: dict, rules: dict | None = None) -> tuple[str, list[str]]:
    """يحدد النظام الضريبي الفعلي (ifu أو reel) مع رسائل توضيحية."""
    rules = rules or rules_mod.tax_rules()
    notes: list[str] = []
    want = p["tax"]["regime"]
    if want == "reel":
        return "reel", notes
    if p["legal_form"] == "company":
        if want == "ifu":
            notes.append("الشركات لا تخضع لنظام IFU، لذلك طُبّق النظام الحقيقي.")
        return "reel", notes
    # تقدير الإيراد السنوي الأول
    T = p["horizon"]
    sh = Shocks.scalar().resolved(T)
    rev = _sales(p, sh, T, 1)["revenue"]
    y1 = float(rev[0, :12].sum())
    ceiling = rules["ifu"]["ceiling"]
    if y1 > ceiling:
        notes.append("الإيراد المتوقع للسنة الأولى يتجاوز سقف IFU، لذلك طُبّق النظام الحقيقي.")
        return "reel", notes
    return "ifu", notes


def _sales(p: dict, sh: Shocks, T: int, N: int) -> dict:
    """المبيعات والتكاليف المتغيرة حسب المنتج."""
    t = np.arange(T)
    season = seasonal_vector(p, T)
    pg = p["macro"]["price_growth"] / 100.0
    ci = p["macro"]["cost_inflation"] / 100.0
    price_trend = (1 + pg) ** (t / 12.0)
    cost_trend = (1 + ci) ** (t / 12.0)

    zero = np.zeros((N, T))
    tot = {k: zero.copy() for k in ("units", "revenue", "cogs", "vat_out", "vat_in_rate_num")}
    by_prod: dict[str, dict[str, np.ndarray]] = {}
    for pr in p["products"]:
        base = pr["units"] * (1 + pr["growth"] / 100.0) ** t
        if pr["seasonal"]:
            base = base * season
        base = base * (t >= pr["launch_month"] - 1)
        units = base[None, :] * sh.demand
        price = pr["price"] * price_trend[None, :] * sh.price
        ucost = pr["unit_cost"] * cost_trend[None, :] * sh.cost
        rev = units * price
        cogs = units * ucost
        by_prod[pr["id"]] = {"units": units, "revenue": rev, "cogs": cogs}
        tot["units"] += units
        tot["revenue"] += rev
        tot["cogs"] += cogs
        tot["vat_out"] += rev * pr["vat_rate"] / 100.0
        tot["vat_in_rate_num"] += cogs * pr["cost_vat_rate"] / 100.0
    tot["by_product"] = by_prod
    return tot


def _payroll(p: dict, T: int, sh: Shocks) -> np.ndarray:
    t = np.arange(T)
    raise_ = p["payroll"]["annual_raise"] / 100.0
    emp = 1 + p["payroll"]["employer_rate"] / 100.0
    cost = np.zeros(T)
    for s in p["staff"]:
        active = (t >= s["start_month"] - 1)
        cost += active * s["count"] * s["gross"] * emp * (1 + raise_) ** (t // 12)
    return cost


def _fixed(p: dict, T: int) -> np.ndarray:
    t = np.arange(T)
    cost = np.zeros(T)
    for f in p["fixed_costs"]:
        active = (t >= f["start_month"] - 1)
        cost += active * f["amount"] * (1 + f["annual_growth"] / 100.0) ** (t // 12)
    return cost


def run_forecast(p: dict, shocks: Shocks | None = None, regime: str | None = None,
                 rules: dict | None = None) -> Forecast:
    rules = rules or rules_mod.tax_rules()
    T = p["horizon"]
    sh = (shocks or Shocks.scalar()).resolved(T)
    N = sh.n
    notes: list[str] = []
    if regime is None:
        regime, notes = resolve_regime(p, rules)
    ifu = regime == "ifu"
    vat_active = not (ifu and rules["ifu"].get("vat_exempt", True))

    s = _sales(p, sh, T, N)
    revenue, cogs, units = s["revenue"], s["cogs"], s["units"]
    vat_out = s["vat_out"] if vat_active else np.zeros((N, T))
    with np.errstate(divide="ignore", invalid="ignore"):
        cost_vat_ratio = np.where(cogs > 0, s["vat_in_rate_num"] / np.where(cogs > 0, cogs, 1), 0.0)
    if not vat_active:
        cost_vat_ratio = np.zeros((N, T))

    # ----- مخزون ومشتريات
    wc = p["working_capital"]
    target = wc["inventory_days"] / 30.0 * cogs
    target_prev = np.concatenate([target[:, :1], target[:, :-1]], axis=1)
    purchases = np.maximum(cogs + (target - target_prev), 0.0)
    inv_open = target_prev[:, 0].copy()
    inv_level = inv_open[:, None] + np.cumsum(purchases - cogs, axis=1)
    vat_in = purchases * cost_vat_ratio

    # ----- تحصيل وسداد
    cust_lag = np.maximum(wc["customer_days"] + sh.collect_add, 0.0) / 30.0
    supp_lag = np.maximum(wc["supplier_days"] + sh.supply_add, 0.0) / 30.0
    billed = revenue + vat_out
    collections = lag_series(billed, cust_lag)
    supp_bill = purchases + vat_in
    supplier_paid = lag_series(supp_bill, supp_lag)
    receivables = np.cumsum(billed - collections, axis=1)
    payables = np.cumsum(supp_bill - supplier_paid, axis=1)

    # ----- تكاليف تشغيلية
    payroll = np.broadcast_to(_payroll(p, T, sh), (N, T)).copy()
    fixed = _fixed(p, T)[None, :] * sh.fixed
    one_off = np.zeros(T)
    for o in p["one_offs"]:
        one_off[o["month"] - 1] += o["amount"]
    one_off = np.broadcast_to(one_off, (N, T)).copy()
    opex = payroll + fixed + one_off
    gross_profit = revenue - cogs
    ebitda = gross_profit - opex

    # ----- استثمارات واهتلاك
    capex = np.zeros(T)
    cum_dep_new = np.zeros(T)
    t = np.arange(T)
    for c in p["capex"]:
        capex[c["month"] - 1] += c["amount"]
        monthly = c["amount"] / (c["life_years"] * 12.0)
        cum_dep_new += np.minimum(c["amount"], monthly * np.maximum(0, t - (c["month"] - 1)))
    open_assets = p["opening_fixed_assets"]
    dep_open_cum = np.minimum(open_assets, open_assets / (5 * 12.0) * (t + 1)) if open_assets > 0 else np.zeros(T)
    cum_dep = cum_dep_new + dep_open_cum
    dep = np.diff(np.concatenate([[0.0], cum_dep]))
    depreciation = np.broadcast_to(dep, (N, T)).copy()
    capex_b = np.broadcast_to(capex, (N, T)).copy()
    fixed_assets = open_assets + np.cumsum(capex) - cum_dep
    fixed_assets = np.broadcast_to(fixed_assets, (N, T)).copy()
    ebit = ebitda - depreciation

    # ----- قروض
    L = loans_mod.aggregate(p["loans"], T)
    interest = np.broadcast_to(L["interest"], (N, T)).copy()
    loan_disb = np.broadcast_to(L["disb"], (N, T)).copy()
    loan_repay = np.broadcast_to(L["principal"], (N, T)).copy()
    loan_bal = np.broadcast_to(L["balance"], (N, T)).copy()
    loan_open = float(L["opening"])
    ebt = ebit - interest

    # ----- ضرائب
    if ifu:
        rates = rules["ifu"]["rates"]
        num = np.zeros((N, T))
        for pr in p["products"]:
            num += s["by_product"][pr["id"]]["revenue"] * rates[pr["activity"]] / 100.0
        tax = np.maximum(num, rules["ifu"]["minimum_annual"] / 12.0)
    else:
        rate = rules_mod.ibs_rate_for(p) / 100.0
        cum_ebt = np.cumsum(ebt, axis=1)
        cum_tax = np.maximum.accumulate(rate * np.maximum(cum_ebt, 0.0), axis=1)
        tax = np.diff(np.concatenate([np.zeros((N, 1)), cum_tax], axis=1), axis=1)
    tax_paid = np.concatenate([np.zeros((N, 1)), tax[:, :-1]], axis=1)
    tax_payable = np.cumsum(tax - tax_paid, axis=1)
    net_income = ebt - tax

    # ----- TVA مع ترحيل الرصيد الدائن
    vat_paid = np.zeros((N, T))
    if vat_active:
        credit = np.zeros(N)
        due_prev = np.zeros(N)
        for k in range(T):
            vat_paid[:, k] = due_prev
            bal = (vat_out[:, k] - vat_in[:, k]) - credit
            due = np.maximum(bal, 0.0)
            credit = np.maximum(-bal, 0.0)
            due_prev = due
    vat_liab = np.cumsum(vat_out - vat_in - vat_paid, axis=1)

    # ----- مساهمات الملاك
    eq = np.zeros(T)
    for e in p["equity_injections"]:
        eq[e["month"] - 1] += e["amount"]
    equity_inj = np.broadcast_to(eq, (N, T)).copy()

    # ----- تدفقات نقدية
    cfo = collections - supplier_paid - opex - vat_paid - tax_paid - interest
    cfi = -capex_b
    cff = loan_disb - loan_repay + equity_inj
    net_cf = cfo + cfi + cff
    cash = p["start_cash"] + np.cumsum(net_cf, axis=1)

    # ----- ميزانية
    loans_bal = loan_bal.copy()
    if loan_open > 0:
        # القروض القائمة: الرصيد المتبقي يظهر في loan_bal مباشرة
        pass
    total_assets = cash + receivables + inv_level + fixed_assets
    total_liab = payables + vat_liab + tax_payable + loans_bal
    equity0 = p["start_cash"] + inv_open + open_assets - loan_open
    equity = equity0[:, None] + np.cumsum(net_income, axis=1) + np.cumsum(equity_inj, axis=1)
    check = total_assets - (total_liab + equity)

    a = {
        "units": units, "revenue": revenue, "vat_out": vat_out, "cogs": cogs, "gross_profit": gross_profit,
        "payroll": payroll, "fixed": fixed, "one_off": one_off, "opex": opex, "ebitda": ebitda,
        "depreciation": depreciation, "ebit": ebit, "interest": interest, "ebt": ebt, "tax": tax,
        "net_income": net_income, "collections": collections, "supplier_paid": supplier_paid,
        "vat_paid": vat_paid, "tax_paid": tax_paid, "capex": capex_b, "loan_disb": loan_disb,
        "loan_repay": loan_repay, "equity_inj": equity_inj, "cfo": cfo, "cfi": cfi, "cff": cff,
        "net_cash_flow": net_cf, "purchases": purchases,
        "cash": cash, "receivables": receivables, "inventory": inv_level, "fixed_assets": fixed_assets,
        "total_assets": total_assets, "payables": payables, "vat_liab": vat_liab,
        "tax_payable": tax_payable, "loans": loans_bal, "total_liabilities": total_liab,
        "equity": equity, "check": check,
    }
    meta = {
        "T": T, "N": N, "regime": regime, "vat_active": vat_active, "notes": notes,
        "by_product": {k: {kk: vv for kk, vv in v.items()} for k, v in s["by_product"].items()},
        "inv_open": inv_open, "loan_open": loan_open, "equity0": equity0,
    }
    return Forecast(a, meta)
