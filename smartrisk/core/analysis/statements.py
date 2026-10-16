"""القوائم المالية الثلاث (دخل، تدفقات، ميزانية) شهرياً وسنوياً."""
from __future__ import annotations

from ..registry import analyzer

# (المفتاح، العنوان، نوع: flow/stock، إشارة العرض، مستوى: 0 عادي / 1 إجمالي)
INCOME = [
    ("revenue", "الإيرادات", "flow", 0), ("cogs", "تكلفة البضاعة المباعة", "flow", 0),
    ("gross_profit", "الربح الإجمالي", "flow", 1), ("payroll", "الأجور والأعباء", "flow", 0),
    ("fixed", "التكاليف الثابتة", "flow", 0), ("one_off", "مصاريف استثنائية", "flow", 0),
    ("ebitda", "الربح قبل الفوائد والضرائب والاهتلاك (EBITDA)", "flow", 1),
    ("depreciation", "الاهتلاك", "flow", 0), ("ebit", "الربح التشغيلي (EBIT)", "flow", 1),
    ("interest", "فوائد القروض", "flow", 0), ("ebt", "الربح قبل الضريبة", "flow", 1),
    ("tax", "الضريبة (IFU / IBS)", "flow", 0), ("net_income", "الربح الصافي", "flow", 1),
]
CASHFLOW = [
    ("collections", "المقبوضات من الزبائن", "flow", 0), ("supplier_paid", "المدفوعات للموردين", "flow", 0),
    ("payroll", "الأجور والأعباء", "flow", 0), ("fixed", "التكاليف الثابتة", "flow", 0),
    ("one_off", "مصاريف استثنائية", "flow", 0), ("vat_paid", "TVA المسدّدة", "flow", 0),
    ("tax_paid", "الضريبة المسدّدة", "flow", 0), ("interest", "فوائد القروض", "flow", 0),
    ("cfo", "التدفق التشغيلي", "flow", 1), ("capex", "الاستثمارات", "flow", 0),
    ("cfi", "التدفق الاستثماري", "flow", 1), ("loan_disb", "قروض مستلمة", "flow", 0),
    ("loan_repay", "أقساط القروض", "flow", 0), ("equity_inj", "مساهمات الملاك", "flow", 0),
    ("cff", "التدفق التمويلي", "flow", 1), ("net_cash_flow", "صافي التدفق النقدي", "flow", 1),
    ("cash", "الرصيد النقدي آخر المدة", "stock", 1),
]
BALANCE = [
    ("cash", "الخزينة", "stock", 0), ("receivables", "الزبائن (مدينون)", "stock", 0),
    ("inventory", "المخزون", "stock", 0), ("fixed_assets", "الأصول الثابتة (صافي)", "stock", 0),
    ("total_assets", "مجموع الأصول", "stock", 1), ("payables", "الموردون (دائنون)", "stock", 0),
    ("vat_liab", "TVA المستحقة", "stock", 0), ("tax_payable", "الضرائب المستحقة", "stock", 0),
    ("loans", "القروض", "stock", 0), ("total_liabilities", "مجموع الخصوم", "stock", 1),
    ("equity", "الأموال الخاصة", "stock", 1),
]
# عند عرض التدفقات تظهر المصاريف بإشارة سالبة
NEGATE_IN_CASHFLOW = {"supplier_paid", "payroll", "fixed", "one_off", "vat_paid", "tax_paid", "interest", "capex", "loan_repay"}


def _lines(fc, defs, negate=frozenset()):
    out = []
    T = fc.T
    for key, label, kind, total in defs:
        sign = -1.0 if key in negate else 1.0
        arr = fc.a[key][0] * sign
        years = [float((arr[y * 12:(y + 1) * 12][-1]) if kind == "stock" else arr[y * 12:(y + 1) * 12].sum())
                 for y in range(-(-T // 12))]
        out.append({"key": key, "label": label, "total": bool(total), "kind": kind,
                    "monthly": arr.tolist(), "annual": years})
    return out


@analyzer("statements", title="القوائم المالية")
def statements(ctx, params):
    fc = ctx.forecast()
    p = ctx.project
    by_prod = []
    for pr in p["products"]:
        d = fc.meta["by_product"][pr["id"]]
        by_prod.append({"id": pr["id"], "name": pr["name"],
                        "revenue": d["revenue"][0].tolist(), "units": d["units"][0].tolist()})
    return {
        "months": list(range(1, fc.T + 1)), "years": list(range(1, -(-fc.T // 12) + 1)),
        "regime": fc.meta["regime"], "regime_notes": fc.meta["notes"], "vat_active": fc.meta["vat_active"],
        "income": _lines(fc, INCOME), "cashflow": _lines(fc, CASHFLOW, NEGATE_IN_CASHFLOW), "balance": _lines(fc, BALANCE),
        "by_product": by_prod, "balance_check": float(abs(fc.a["check"]).max()),
    }
