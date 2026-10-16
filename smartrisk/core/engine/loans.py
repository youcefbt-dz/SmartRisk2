"""جداول سداد القروض (أقساط ثابتة مع فترة إمهال اختيارية)."""
from __future__ import annotations

import numpy as np


def payment(principal: float, monthly_rate: float, n: int) -> float:
    if n <= 0:
        return 0.0
    if monthly_rate <= 1e-12:
        return principal / n
    return principal * monthly_rate / (1.0 - (1.0 + monthly_rate) ** (-n))


def loan_schedule(loan: dict, horizon: int) -> dict[str, np.ndarray]:
    """يعيد مصفوفات (horizon,): صرف القرض، الفائدة، أصل الدين المسدّد، الرصيد، والرصيد الافتتاحي.

    - قرض جديد: يُصرف في شهر البداية ويبدأ السداد في الشهر الذي يليه.
    - قرض قائم (existing): رصيده الافتتاحي = المبلغ ويبدأ السداد من الشهر الأول دون صرف جديد.
    """
    T = horizon
    disb = np.zeros(T)
    interest = np.zeros(T)
    principal_paid = np.zeros(T)
    balance = np.zeros(T)
    opening = 0.0

    P = float(loan["principal"])
    n = int(loan["months"])
    g = int(loan["grace"])
    r = float(loan["rate"]) / 100.0 / 12.0
    if P <= 0 or n <= 0:
        return {"disb": disb, "interest": interest, "principal": principal_paid, "balance": balance, "opening": 0.0}

    s = int(loan["start_month"]) - 1
    if loan.get("existing"):
        first = 0
        opening = P
        bal = P
        balance[:] = 0.0
    else:
        first = s + 1
        if s < T:
            disb[s] = P
        bal = P
        # الرصيد في شهر الصرف
        if s < T:
            balance[s] = P

    pmt = payment(P, r, n - g)
    for j in range(n):
        idx = first + j
        if idx >= T:
            break
        i = bal * r
        if j < g:
            pr = 0.0
        elif j == n - 1:
            pr = bal
        else:
            pr = min(bal, pmt - i)
        bal -= pr
        interest[idx] = i
        principal_paid[idx] = pr
        balance[idx] = bal
    # حفظ الرصيد بعد نهاية جدول السداد داخل الأفق
    if first + n < T:
        balance[first + n:] = 0.0
    return {"disb": disb, "interest": interest, "principal": principal_paid, "balance": balance, "opening": opening}


def aggregate(loans: list[dict], horizon: int) -> dict[str, np.ndarray | float]:
    T = horizon
    out = {k: np.zeros(T) for k in ("disb", "interest", "principal", "balance")}
    opening = 0.0
    for ln in loans:
        s = loan_schedule(ln, T)
        for k in out:
            out[k] += s[k]
        opening += s["opening"]
    out["opening"] = opening  # type: ignore[assignment]
    return out
