"""مقارنة مصادر التمويل بنفس السيناريوهات العشوائية (Common Random Numbers)."""
from __future__ import annotations

import math
from copy import deepcopy

import numpy as np

from ..engine import rules as rules_mod
from ..engine.schema import new_id
from ..registry import analyzer
from .montecarlo import get_mc, summarize


def _dscr(fc) -> float | None:
    a = fc.a
    ds = float(a["interest"][0, :12].sum() + a["loan_repay"][0, :12].sum())
    if ds <= 1e-6:
        return None
    return float((a["ebitda"][0, :12].sum() - a["tax"][0, :12].sum()) / ds)


def _eval(ctx, proj: dict, n: int, seed: int) -> dict:
    fc = ctx.forecast(proj)
    mc = summarize(get_mc(ctx, n, seed, project=proj))
    a = fc.a
    return {
        "min_cash": float(a["cash"][0].min()),
        "final_cash": float(a["cash"][0, -1]),
        "final_equity": float(a["equity"][0, -1]),
        "total_interest": float(a["interest"][0].sum()),
        "dscr": _dscr(fc),
        "p_ruin_12": mc["p_ruin_12"], "p_ruin_horizon": mc["p_ruin_horizon"],
        "car95": mc["cash_at_risk_95"],
    }


@analyzer("financing", title="مقارنة مصادر التمويل")
def financing(ctx, params):
    p = ctx.project
    n = int(min(3000, max(300, params.get("n", 1500))))
    seed = int(params.get("seed", 42))
    base_mc = summarize(get_mc(ctx, n, seed))
    amount = params.get("amount")
    if amount in (None, ""):
        amount = math.ceil(base_mc["cash_at_risk_95"] / 50000) * 50000
    amount = max(0.0, float(amount))
    start = int(params.get("start_month", 1))

    baseline = _eval(ctx, p, n, seed)
    baseline.update({"id": "none", "name": "بدون تمويل إضافي", "kind": "none", "funded": 0.0,
                     "dilution": None, "verified": True, "note": ""})
    rows = [baseline]
    pre_money = float(params.get("pre_money", p["valuation"]["pre_money"]) or 0)
    for opt in rules_mod.funding_programs()["options"]:
        q = deepcopy(p)
        cap = opt.get("max_amount")
        funded = min(amount, cap) if cap else amount
        rate = float(params.get(f"rate_{opt['id']}", opt["rate"]))
        if funded > 0:
            if opt["kind"] == "loan":
                q["loans"].append({"id": new_id(), "name": opt["name"], "principal": funded, "rate": rate,
                                   "months": opt["months"], "grace": opt.get("grace", 0), "start_month": start, "existing": False})
            else:
                q["equity_injections"].append({"id": new_id(), "name": opt["name"], "amount": funded, "month": start})
        ev = _eval(ctx, q, n, seed)
        dilution = None
        if opt["id"] == "partner" and funded > 0 and pre_money > 0:
            dilution = funded / (pre_money + funded)
        note = opt.get("cost_note", "")
        if cap and amount > cap:
            note += f" (السقف {cap:,.0f} دج؛ لم يُغطَّ {amount - cap:,.0f} دج)."
        ev.update({"id": opt["id"], "name": opt["name"], "kind": opt["kind"], "funded": funded,
                   "rate": rate if opt["kind"] == "loan" else None,
                   "months": (opt.get("months") or None) if opt["kind"] == "loan" else None,
                   "dilution": dilution, "verified": opt.get("verified", False), "note": note.strip()})
        rows.append(ev)

    # التوصية: أقل تكلفة (فوائد + تخفيف ملكية) ضمن احتمال نفاد ≤ 5%، وإلا الأقل احتمالاً
    cands = [r for r in rows if r["id"] != "none" and r["funded"] > 0]
    rec = None
    if cands:
        ok = [r for r in cands if r["p_ruin_12"] <= 0.05]
        pool = ok or cands
        def cost(r):
            equity_cost = (r["dilution"] or 0) * max(0.0, r["final_equity"])
            return r["total_interest"] + equity_cost
        rec = min(pool, key=(cost if ok else (lambda r: (r["p_ruin_12"], cost(r)))))["id"]
    return {"amount": amount, "start_month": start, "baseline_p_ruin_12": base_mc["p_ruin_12"],
            "baseline_car95": base_mc["cash_at_risk_95"], "options": rows, "recommended": rec,
            "pre_money": pre_money, "verify_note": "قيم برامج التمويل إرشادية وغير مؤكدة؛ راجع الجهة قبل القرار."}
