"""درجة جاهزية التمويل + مؤشرات الإنذار المبكر (KRIs)."""
from __future__ import annotations

from ..engine import rules as rules_mod
from ..registry import analyzer
from ..util import LEVEL_AR, SEVERITY, level_of, lerp_score, worst
from .montecarlo import get_mc, summarize


def full_metrics(ctx) -> dict:
    """المؤشرات الأساسية + مخرجات المحاكاة المضغوطة في قاموس واحد."""
    def build():
        m = dict(ctx.metrics())
        mc = summarize(get_mc(ctx))
        m.update({
            "p_ruin_6": mc["p_ruin_6"], "p_ruin_12": mc["p_ruin_12"],
            "p_ruin_horizon": mc["p_ruin_horizon"], "p_survive_12": mc["p_survive_12"],
            "cash_at_risk_95": mc["cash_at_risk_95"],
        })
        return m
    return ctx.memo("full_metrics", build)


def _explain(cid: str, v, m: dict) -> str:
    pct = lambda x: f"{x * 100:.0f}%"  # noqa: E731
    if cid == "profit":
        return f"هامش الربح الصافي في السنة الأولى {pct(v)}. المريح للممولين نحو 20%."
    if cid == "safety":
        return "لا توجد نقطة تعادل قابلة للحساب." if v is None else f"يمكن أن تنخفض مبيعاتك {pct(v)} قبل أن تخسر. الهدف 40%."
    if cid == "liquidity":
        return f"السيولة الحالية تغطي {v:.1f} شهراً من الالتزامات الثابتة. الهدف 4 أشهر."
    if cid == "resilience":
        return f"في {pct(v)} من سيناريوهات المحاكاة لا تنفد السيولة خلال 12 شهراً. الهدف 95%."
    if cid == "debt":
        return "لا توجد أقساط قروض." if v is None else f"التدفق التشغيلي يغطي خدمة الدين {v:.1f} مرة. المصارف تفضل مرتين أو أكثر."
    if cid == "workingcap":
        return f"دورة التحويل النقدي {v:.0f} يوماً (تحصيل + مخزون − سداد). الهدف 30 يوماً أو أقل."
    return ""


@analyzer("scoring", title="جاهزية التمويل")
def scoring(ctx, params):
    sd = rules_mod.scoring_def()
    m = full_metrics(ctx)
    comps = []
    total = 0.0
    for c in sd["components"]:
        v = m.get(c["metric"])
        s = lerp_score(v, c["bad"], c["good"], c.get("none_value"))
        pts = s * c["weight"]
        total += pts
        lvl = "safe" if s >= 0.7 else "warn" if s >= 0.4 else "crit"
        comps.append({
            "id": c["id"], "title": c["title"], "value": v, "score": s, "points": pts, "weight": c["weight"],
            "level": lvl, "term": c.get("term"), "text": _explain(c["id"], v, m),
            "action": c["action"] if lvl != "safe" else "",
        })
    wsum = sum(c["weight"] for c in sd["components"]) or 1
    total = total / wsum * 100
    lv = sd["levels"]
    level = "safe" if total >= lv["ready"] else "warn" if total >= lv["almost"] else "crit"
    verdict = {"safe": "جاهز للتقديم", "warn": "شبه جاهز", "crit": "يحتاج تحسيناً قبل التقديم"}[level]
    return {"score": total, "level": level, "verdict": verdict, "components": comps}


@analyzer("kri", title="مؤشرات الإنذار المبكر")
def kri(ctx, params):
    m = full_metrics(ctx)
    items = []
    for d in rules_mod.kri_defs():
        v = m.get(d["metric"])
        if v is None and d.get("optional"):
            continue
        lvl = level_of(v, d["warn"], d["crit"], d["direction"])
        scale = d.get("scale", 1)
        items.append({
            "id": d["id"], "title": d["title"], "level": lvl, "label": LEVEL_AR[lvl],
            "value": None if v is None else v * scale, "unit": d["unit"], "term": d.get("term"),
            "warn": d["warn"] * scale, "crit": d["crit"] * scale, "direction": d["direction"], "hint": d["hint"],
        })
    items.sort(key=lambda i: -SEVERITY[i["level"]])
    return {"items": items, "overall": worst([i["level"] for i in items])}
