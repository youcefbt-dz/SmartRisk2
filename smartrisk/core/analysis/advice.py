"""محرك النصائح: قواعد صغيرة مستقلة. لإضافة نصيحة جديدة أضف دالة مزيّنة بـ @rule."""
from __future__ import annotations

from typing import Callable

from ..registry import analyzer
from ..util import LEVEL_AR, SEVERITY
from .decisions import pricing
from .montecarlo import get_mc, summarize
from .scoring import full_metrics

RULES: list[tuple[int, Callable]] = []


def rule(priority: int = 50):
    def deco(fn):
        RULES.append((priority, fn))
        return fn
    return deco


def dz(x: float) -> str:
    return f"{x:,.0f} دج"


def adv(id_, level, area, title, text, action="") -> dict:
    return {"id": id_, "level": level, "label": LEVEL_AR[level], "area": area, "title": title, "text": text, "action": action}


class R:
    """حزمة المدخلات المشتركة لكل القواعد."""
    def __init__(self, ctx):
        self.ctx = ctx
        self.p = ctx.project
        self.m = full_metrics(ctx)
        self.mc = summarize(get_mc(ctx))
        self.fc = ctx.forecast()
        self._pricing = None

    @property
    def pricing(self):
        if self._pricing is None:
            self._pricing = pricing(self.ctx, {})
        return self._pricing


@rule(10)
def liquidity(r: R):
    m, mc = r.m, r.mc
    if m["cash_out_month"]:
        need = -m["min_cash"]
        yield adv("cash_out", "crit", "السيولة", "السيولة تنفد في التوقع الأساسي",
                  f"يصبح الرصيد سالباً في الشهر {m['cash_out_month']}، وأدنى رصيد {dz(m['min_cash'])}.",
                  f"وفّر نحو {dz(need)} قبل ذلك الشهر عبر تمويل قصير الأجل أو تأجيل مصاريف أو تسريع التحصيل.")
    p12 = mc["p_ruin_12"]
    if p12 > 0.2:
        yield adv("mc_risk", "crit", "المخاطر", "احتمال نفاد السيولة مرتفع",
                  f"في {p12 * 100:.0f}% من سيناريوهات المحاكاة ينفد الرصيد خلال 12 شهراً.",
                  f"احتفظ باحتياطي لا يقل عن {dz(mc['cash_at_risk_95'])} لتبلغ درجة أمان 95%.")
    elif p12 > 0.05:
        yield adv("mc_risk", "warn", "المخاطر", "خطر نفاد السيولة قائم",
                  f"في {p12 * 100:.0f}% من السيناريوهات ينفد الرصيد خلال 12 شهراً.",
                  f"رفع الاحتياطي بنحو {dz(mc['cash_at_risk_95'])} يخفض الاحتمال إلى أقل من 5%.")
    else:
        yield adv("mc_risk", "safe", "المخاطر", "السيولة صامدة أمام العشوائية",
                  f"احتمال نفاد السيولة خلال 12 شهراً {p12 * 100:.1f}% فقط.")
    if not m["cash_out_month"] and m["runway_months"] < 3:
        yield adv("runway", "warn", "السيولة", "احتياطي السيولة قصير",
                  f"سيولتك تغطي {m['runway_months']:.1f} شهر فقط من الالتزامات الثابتة.",
                  "ابنِ احتياطياً يغطي 3 أشهر على الأقل.")


@rule(20)
def profitability(r: R):
    m = r.m
    nm = m["net_margin_y1"]
    if m["revenue_y1"] <= 0:
        return
    if nm < 0:
        yield adv("margin", "crit", "الربحية", "المشروع خاسر في السنة الأولى",
                  f"هامش الربح الصافي {nm * 100:.0f}% (ربح صافٍ {dz(m['net_income_y1'])}).",
                  "راجع التسعير والتكاليف الثابتة قبل أي توسع.")
    elif nm < 0.08:
        yield adv("margin", "warn", "الربحية", "هامش الربح ضعيف",
                  f"هامش الربح الصافي {nm * 100:.0f}% وهو هش أمام أي صدمة.",
                  "ارفع الأسعار تدريجياً أو خفّض تكلفة الوحدة.")
    else:
        yield adv("margin", "safe", "الربحية", "ربحية جيدة", f"هامش الربح الصافي {nm * 100:.0f}% في السنة الأولى.")
    mos = m["margin_of_safety"]
    if mos is not None and m["revenue_y1"] > 0:
        if mos < 0.1:
            yield adv("mos", "crit", "الهيكل", "هامش الأمان شبه معدوم",
                      f"مبيعاتك أعلى من التعادل بـ {mos * 100:.0f}% فقط.", "اخفض التكاليف الثابتة أو ارفع هامش المساهمة.")
        elif mos < 0.25:
            yield adv("mos", "warn", "الهيكل", "هامش الأمان محدود",
                      f"تتحمل انخفاضاً في المبيعات بنسبة {mos * 100:.0f}% قبل الخسارة.", "الهدف 40% فأكثر.")


@rule(30)
def prices(r: R):
    for pr in r.pricing["products"]:
        if pr["price"] <= 0:
            continue
        if pr["level"] == "crit":
            yield adv(f"price_{pr['id']}", "crit", "التسعير", f"سعر «{pr['name']}» لا يغطي تكلفته الكاملة",
                      f"السعر {dz(pr['price'])} أقل من أدنى سعر بلا خسارة {dz(pr['floor'])}.",
                      f"ارفعه إلى {dz(pr['floor'])} على الأقل، والموصى به {dz(pr['recommended'])}.")
        elif pr["level"] == "warn":
            yield adv(f"price_{pr['id']}", "warn", "التسعير", f"سعر «{pr['name']}» أقل من الموصى به",
                      f"يغطي السعر التكلفة لكن الهامش المستهدف يتطلب {dz(pr['recommended'])}.")


@rule(40)
def debt(r: R):
    d = r.m["dscr"]
    if d is None:
        return
    if d < 1.1:
        yield adv("dscr", "crit", "الدين", "الأقساط تستهلك كامل التدفق التشغيلي",
                  f"تغطية خدمة الدين {d:.1f} مرة فقط.", "لا تأخذ ديناً جديداً، وفاوض على إعادة الجدولة أو فترة إمهال.")
    elif d < 1.5:
        yield adv("dscr", "warn", "الدين", "تغطية خدمة الدين ضيقة",
                  f"التدفق التشغيلي يغطي الأقساط {d:.1f} مرة، والمصارف تفضل 2 فأكثر.")
    for ln in r.p["loans"]:
        if ln["rate"] > 10:
            yield adv(f"rate_{ln['id']}", "warn", "الدين", f"فائدة «{ln['name']}» مرتفعة",
                      f"معدل {ln['rate']:g}% سنوياً. قارن ببرامج الدعم والتمويل المدعوم.")


@rule(50)
def working_capital(r: R):
    m = r.m
    if m["customer_days"] > 75:
        yield adv("dso", "crit", "رأس المال العامل", "تحصيل الزبائن بطيء جداً",
                  f"تنتظر {m['customer_days']:.0f} يوماً لقبض مبيعاتك، فيُجمَّد جزء كبير من السيولة.", "قدّم خصماً للدفع المبكر واطلب عربوناً.")
    elif m["customer_days"] > 45:
        yield adv("dso", "warn", "رأس المال العامل", "مدة التحصيل طويلة",
                  f"متوسط التحصيل {m['customer_days']:.0f} يوماً.", "قصّرها بعروض الدفع الفوري.")
    if m["inventory_days"] > 120:
        yield adv("dio", "crit", "رأس المال العامل", "مخزون راكد",
                  f"يبقى المخزون {m['inventory_days']:.0f} يوماً قبل بيعه.", "قلّل الطلبيات وصرّف البطيء بعروض.")
    elif m["inventory_days"] > 60:
        yield adv("dio", "warn", "رأس المال العامل", "المخزون يستهلك السيولة",
                  f"مدة بقاء المخزون {m['inventory_days']:.0f} يوماً.")
    if m["cash_cycle_days"] > 90:
        yield adv("ccc", "warn", "رأس المال العامل", "دورة التحويل النقدي طويلة",
                  f"تمر {m['cash_cycle_days']:.0f} يوماً بين دفع تكلفة البضاعة وقبض ثمنها.", "فاوض موردك على آجال سداد أطول.")


@rule(60)
def structure(r: R):
    m = r.m
    if m["top_product_share"] > 0.85 and len(r.p["products"]) > 1:
        yield adv("conc", "crit", "التنويع", "اعتماد شبه كامل على منتج واحد",
                  f"{m['top_product_share'] * 100:.0f}% من الإيراد من منتج واحد.", "أضف منتجاً أو خدمة مكمّلة لتوزيع المخاطر.")
    elif m["top_product_share"] > 0.6 and len(r.p["products"]) > 1:
        yield adv("conc", "warn", "التنويع", "تركّز الإيرادات في منتج",
                  f"{m['top_product_share'] * 100:.0f}% من الإيراد من أكبر منتج.")
    if r.p["products"] and not r.p["staff"] and m["revenue_y1"] > 0:
        yield adv("owner_pay", "warn", "الدقة", "لم تُدخل أي أجور",
                  "غياب الأجور (ومنها أجرك الشخصي) يجعل الربح يبدو أعلى من الواقع.", "أضف أجرك ضمن «الموظفون والأجور».")
    seas = r.p["seasonality"]
    if max(seas) / max(min(seas), 0.01) >= 1.6:
        yield adv("season", "warn", "الموسمية", "موسمية قوية في المبيعات",
                  "الفارق بين أقوى شهر وأضعفه كبير، فتتشكّل فجوات سيولة في المواسم الهادئة.", "ادّخر من الأشهر القوية لتغطية الضعيفة.")
    for pr in r.p["products"]:
        if pr["growth"] > 5:
            yield adv(f"growth_{pr['id']}", "warn", "الفرضيات", f"نمو «{pr['name']}» متفائل",
                      f"النمو {pr['growth']:g}% شهرياً يعني مضاعفة المبيعات تقريباً كل {0.693 / max(pr['growth'] / 100, 0.001):.0f} شهراً.",
                      "اختبره بسيناريو أبطأ.")


@rule(70)
def tax_regime(r: R):
    rules = r.ctx.rules
    notes = r.ctx.regime_notes
    for n in notes:
        yield adv("regime_note", "warn", "الضرائب", "تغيّر النظام الضريبي", n)
    if r.ctx.regime == "ifu" and r.m["revenue_y1"] > 0.8 * rules["ifu"]["ceiling"]:
        yield adv("ifu_ceiling", "warn", "الضرائب", "الاقتراب من سقف IFU",
                  f"إيرادك يقترب من سقف النظام الجزافي ({rules['ifu']['ceiling']:,.0f} دج)، وتجاوزه ينقلك للنظام الحقيقي.",
                  "خطّط لمحاسب وحسابات منتظمة مسبقاً.")


@rule(80)
def zscore(r: R):
    z, zone = r.m["z_score"], r.m["z_zone"]
    if z is None:
        return
    if zone == "crit":
        yield adv("z", "crit", "الإفلاس", "مؤشر الإفلاس في منطقة الخطر",
                  f"Z″ = {z:.2f} (أقل من 1.1).", "حسّن الربحية وخفّض الاعتماد على الديون والمطلوبات القصيرة.")
    elif zone == "warn":
        yield adv("z", "warn", "الإفلاس", "مؤشر الإفلاس في المنطقة الرمادية", f"Z″ = {z:.2f} (بين 1.1 و2.6).")


@analyzer("advice", title="النصائح والتقرير")
def advice(ctx, params):
    r = R(ctx)
    items: list[dict] = []
    for _, fn in sorted(RULES, key=lambda t: t[0]):
        items.extend(fn(r))
    order = {"crit": 0, "warn": 1, "safe": 2}
    items.sort(key=lambda a: order[a["level"]])
    todo = [a for a in items if a["level"] != "safe" and a["action"]][:3]
    return {
        "items": items,
        "plan": [{"title": a["title"], "action": a["action"], "level": a["level"]} for a in todo],
        "strengths": [a["title"] for a in items if a["level"] == "safe"],
        "weaknesses": [a["title"] for a in items if a["level"] != "safe"],
    }
