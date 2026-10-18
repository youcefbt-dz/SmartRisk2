"""مخطط بيانات المشروع: القيم الافتراضية والتطبيع والتحقق.

قاعدة موحّدة: كل الحقول المئوية تُخزَّن بوحدة «النسبة المئوية» (مثلاً 19 تعني 19%)
عدا معاملات الموسمية فهي مضاعفات (1.0 = المتوسط).
"""
from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

SECTORS = {
    "commerce": "تجارة",
    "production": "إنتاج / حرفة",
    "services": "خدمات",
    "btph": "بناء وأشغال عمومية",
    "tourism": "سياحة وضيافة",
}
LEGAL_FORMS = {"individual": "شخص طبيعي", "company": "شركة (SARL / EURL ...)"}
ACTIVITIES = {"goods": "بيع سلع", "services": "خدمات"}
REGIMES = {"auto": "تلقائي", "ifu": "الضريبة الجزافية الوحيدة (IFU)", "reel": "النظام الحقيقي"}

MAX_HORIZON = 60
MIN_HORIZON = 12


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def default_project() -> dict:
    return {
        "name": "مشروع جديد",
        "sector": "commerce",
        "legal_form": "individual",
        "city": "",
        "horizon": 36,
        "start_month": 1,
        "start_cash": 0.0,
        "opening_fixed_assets": 0.0,
        "products": [],
        "seasonality": [1.0] * 12,
        "fixed_costs": [],
        "staff": [],
        "payroll": {"employer_rate": 25.0, "annual_raise": 3.0},
        "working_capital": {"customer_days": 15.0, "supplier_days": 20.0, "inventory_days": 20.0},
        "loans": [],
        "capex": [],
        "one_offs": [],
        "equity_injections": [],
        "macro": {"price_growth": 3.0, "cost_inflation": 4.0},
        "tax": {"regime": "auto", "ibs_rate": None},
        "risk": {"uncertainty": 1.0, "demand_vol": 15.0, "cost_vol": 6.0, "price_vol": 2.0, "collection_vol_days": 8.0},
        "valuation": {"discount_rate": 12.0, "terminal_growth": 0.0, "pre_money": 0.0},
        "capacity": {"total": 0.0, "unit_label": "ساعة", "budget": 0.0},
        "actuals": [],
    }


# ---------------------------------------------------------------- coercion
def num(v: Any, default: float = 0.0, lo: float | None = None, hi: float | None = None) -> float:
    try:
        x = float(v)
        if x != x or x in (float("inf"), float("-inf")):
            raise ValueError
    except (TypeError, ValueError):
        x = float(default)
    if lo is not None:
        x = max(lo, x)
    if hi is not None:
        x = min(hi, x)
    return x


def integer(v: Any, default: int = 0, lo: int | None = None, hi: int | None = None) -> int:
    return int(round(num(v, default, lo, hi)))


def text(v: Any, default: str = "", maxlen: int = 80) -> str:
    if v is None:
        return default
    return str(v).strip()[:maxlen] or default


def boolean(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on", "نعم")
    return default


def _rows(raw: Any, limit: int = 60) -> list[dict]:
    if not isinstance(raw, list):
        return []
    return [r for r in raw[:limit] if isinstance(r, dict)]


# ---------------------------------------------------------------- item normalisers
def _product(r: dict, horizon: int) -> dict:
    return {
        "id": text(r.get("id"), new_id(), 16),
        "name": text(r.get("name"), "منتج", 60),
        "activity": r.get("activity") if r.get("activity") in ACTIVITIES else "goods",
        "price": num(r.get("price"), 0, 0, 1e10),
        "unit_cost": num(r.get("unit_cost"), 0, 0, 1e10),
        "units": num(r.get("units"), 0, 0, 1e9),
        "growth": num(r.get("growth"), 0, -30, 50),
        "vat_rate": num(r.get("vat_rate"), 19, 0, 100),
        "cost_vat_rate": num(r.get("cost_vat_rate"), 19, 0, 100),
        "seasonal": boolean(r.get("seasonal"), True),
        "launch_month": integer(r.get("launch_month"), 1, 1, horizon),
        "elasticity": num(r.get("elasticity"), -1.5, -10, 0),
        "max_units": num(r.get("max_units"), 0, 0, 1e9),
        "capacity_per_unit": num(r.get("capacity_per_unit"), 0, 0, 1e6),
    }


def _fixed(r: dict, horizon: int) -> dict:
    return {
        "id": text(r.get("id"), new_id(), 16),
        "name": text(r.get("name"), "مصروف ثابت", 60),
        "amount": num(r.get("amount"), 0, 0, 1e10),
        "annual_growth": num(r.get("annual_growth"), 0, -50, 100),
        "start_month": integer(r.get("start_month"), 1, 1, horizon),
    }


def _staff(r: dict, horizon: int) -> dict:
    return {
        "id": text(r.get("id"), new_id(), 16),
        "role": text(r.get("role"), "موظف", 60),
        "count": num(r.get("count"), 1, 0, 10000),
        "gross": num(r.get("gross"), 0, 0, 1e9),
        "start_month": integer(r.get("start_month"), 1, 1, horizon),
    }


def _loan(r: dict, horizon: int) -> dict:
    months = integer(r.get("months"), 36, 1, 360)
    return {
        "id": text(r.get("id"), new_id(), 16),
        "name": text(r.get("name"), "قرض", 60),
        "principal": num(r.get("principal"), 0, 0, 1e12),
        "rate": num(r.get("rate"), 6, 0, 60),
        "months": months,
        "grace": integer(r.get("grace"), 0, 0, max(0, months - 1)),
        "start_month": integer(r.get("start_month"), 1, 1, horizon),
        "existing": boolean(r.get("existing"), False),
    }


def _capex(r: dict, horizon: int) -> dict:
    return {
        "id": text(r.get("id"), new_id(), 16),
        "name": text(r.get("name"), "استثمار", 60),
        "amount": num(r.get("amount"), 0, 0, 1e12),
        "month": integer(r.get("month"), 1, 1, horizon),
        "life_years": num(r.get("life_years"), 5, 1, 50),
    }


def _oneoff(r: dict, horizon: int) -> dict:
    return {
        "id": text(r.get("id"), new_id(), 16),
        "name": text(r.get("name"), "مصروف استثنائي", 60),
        "amount": num(r.get("amount"), 0, 0, 1e12),
        "month": integer(r.get("month"), 1, 1, horizon),
    }


def _actual(r: dict, horizon: int) -> dict:
    return {
        "month": integer(r.get("month"), 1, 1, horizon),
        "revenue": num(r.get("revenue"), 0, 0, 1e13),
        "variable_costs": num(r.get("variable_costs"), 0, 0, 1e13),
        "fixed_costs": num(r.get("fixed_costs"), 0, 0, 1e13),
        "cash": None if r.get("cash") in (None, "") else num(r.get("cash"), 0, -1e13, 1e13),
    }


def _equity(r: dict, horizon: int) -> dict:
    return {
        "id": text(r.get("id"), new_id(), 16),
        "name": text(r.get("name"), "مساهمة", 60),
        "amount": num(r.get("amount"), 0, 0, 1e12),
        "month": 1,  # المساهمة في رأس المال تدخل عند انطلاق المشروع، بلا مدة ولا شهر
    }


# ---------------------------------------------------------------- normalise
def normalize(raw: Any) -> tuple[dict, list[str]]:
    """يحوّل أي مدخل إلى مشروع صالح للمحرك. يرجع (المشروع، قائمة التحذيرات)."""
    warnings: list[str] = []
    d = default_project()
    if not isinstance(raw, dict):
        return d, ["بيانات المشروع غير صالحة، استُخدمت القيم الافتراضية."]

    horizon = integer(raw.get("horizon"), d["horizon"], MIN_HORIZON, MAX_HORIZON)
    p: dict = {
        "name": text(raw.get("name"), d["name"], 60),
        "sector": raw.get("sector") if raw.get("sector") in SECTORS else d["sector"],
        "legal_form": raw.get("legal_form") if raw.get("legal_form") in LEGAL_FORMS else d["legal_form"],
        "city": text(raw.get("city"), "", 40),
        "horizon": horizon,
        "start_month": integer(raw.get("start_month"), 1, 1, 12),
        "start_cash": num(raw.get("start_cash"), 0, 0, 1e13),
        "opening_fixed_assets": num(raw.get("opening_fixed_assets"), 0, 0, 1e13),
    }
    p["products"] = [_product(r, horizon) for r in _rows(raw.get("products"), 30)]
    p["fixed_costs"] = [_fixed(r, horizon) for r in _rows(raw.get("fixed_costs"))]
    p["staff"] = [_staff(r, horizon) for r in _rows(raw.get("staff"))]
    p["loans"] = [_loan(r, horizon) for r in _rows(raw.get("loans"), 20)]
    p["capex"] = [_capex(r, horizon) for r in _rows(raw.get("capex"), 30)]
    p["one_offs"] = [_oneoff(r, horizon) for r in _rows(raw.get("one_offs"), 30)]
    p["equity_injections"] = [_equity(r, horizon) for r in _rows(raw.get("equity_injections"), 20)]

    acts: dict[int, dict] = {}
    for r in _rows(raw.get("actuals"), 120):
        a = _actual(r, horizon)
        acts[a["month"]] = a
    p["actuals"] = [acts[k] for k in sorted(acts)]

    seas = raw.get("seasonality")
    if isinstance(seas, list) and len(seas) == 12:
        p["seasonality"] = [num(x, 1.0, 0.0, 10.0) for x in seas]
    else:
        p["seasonality"] = [1.0] * 12
    if sum(p["seasonality"]) <= 0:
        p["seasonality"] = [1.0] * 12

    pr = raw.get("payroll") if isinstance(raw.get("payroll"), dict) else {}
    p["payroll"] = {
        "employer_rate": num(pr.get("employer_rate"), d["payroll"]["employer_rate"], 0, 100),
        "annual_raise": num(pr.get("annual_raise"), d["payroll"]["annual_raise"], -20, 50),
    }
    wc = raw.get("working_capital") if isinstance(raw.get("working_capital"), dict) else {}
    p["working_capital"] = {
        "customer_days": num(wc.get("customer_days"), d["working_capital"]["customer_days"], 0, 365),
        "supplier_days": num(wc.get("supplier_days"), d["working_capital"]["supplier_days"], 0, 365),
        "inventory_days": num(wc.get("inventory_days"), d["working_capital"]["inventory_days"], 0, 365),
    }
    mc = raw.get("macro") if isinstance(raw.get("macro"), dict) else {}
    p["macro"] = {
        "price_growth": num(mc.get("price_growth"), d["macro"]["price_growth"], -20, 100),
        "cost_inflation": num(mc.get("cost_inflation"), d["macro"]["cost_inflation"], -20, 100),
    }
    tx = raw.get("tax") if isinstance(raw.get("tax"), dict) else {}
    ibs = tx.get("ibs_rate")
    p["tax"] = {
        "regime": tx.get("regime") if tx.get("regime") in REGIMES else "auto",
        "ibs_rate": None if ibs in (None, "") else num(ibs, 0, 0, 100),
    }
    rk = raw.get("risk") if isinstance(raw.get("risk"), dict) else {}
    p["risk"] = {
        "uncertainty": num(rk.get("uncertainty"), 1.0, 0.1, 4.0),
        "demand_vol": num(rk.get("demand_vol"), d["risk"]["demand_vol"], 0, 100),
        "cost_vol": num(rk.get("cost_vol"), d["risk"]["cost_vol"], 0, 100),
        "price_vol": num(rk.get("price_vol"), d["risk"]["price_vol"], 0, 100),
        "collection_vol_days": num(rk.get("collection_vol_days"), d["risk"]["collection_vol_days"], 0, 120),
    }
    vl = raw.get("valuation") if isinstance(raw.get("valuation"), dict) else {}
    p["valuation"] = {
        "discount_rate": num(vl.get("discount_rate"), d["valuation"]["discount_rate"], 0, 100),
        "terminal_growth": num(vl.get("terminal_growth"), 0, -10, 20),
        "pre_money": num(vl.get("pre_money"), 0, 0, 1e13),
    }
    cp = raw.get("capacity") if isinstance(raw.get("capacity"), dict) else {}
    p["capacity"] = {
        "total": num(cp.get("total"), 0, 0, 1e9),
        "unit_label": text(cp.get("unit_label"), "ساعة", 20),
        "budget": num(cp.get("budget"), 0, 0, 1e13),
    }

    warnings.extend(validate(p))
    return p, warnings


def validate(p: dict) -> list[str]:
    """تحذيرات لغوية للمستخدم (لا تمنع الحساب)."""
    w: list[str] = []
    if not p["products"]:
        w.append("لم تُضف أي منتج أو خدمة بعد، لذلك الإيرادات صفر.")
    for pr in p["products"]:
        if pr["price"] > 0 and pr["unit_cost"] > pr["price"]:
            w.append(f"«{pr['name']}»: تكلفة الوحدة أعلى من سعر البيع، فكل وحدة تُباع بخسارة.")
        if pr["price"] <= 0 and pr["units"] > 0:
            w.append(f"«{pr['name']}»: سعر البيع صفر مع مبيعات موجبة.")
        if pr["growth"] > 8:
            w.append(f"«{pr['name']}»: نمو {pr['growth']:g}% شهرياً مرتفع جداً ويتضاعف سريعاً، تأكد من واقعيته.")
    if p["start_cash"] <= 0:
        w.append("السيولة الابتدائية صفر؛ ستُعتبر كل المصاريف الأولى عجزاً نقدياً.")
    return w
