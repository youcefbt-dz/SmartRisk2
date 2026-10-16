"""أدوات مشتركة صغيرة."""
from __future__ import annotations

import math
from typing import Any

import numpy as np


def jsonable(x: Any) -> Any:
    """يحوّل numpy وnan/inf إلى قيم JSON آمنة."""
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return jsonable(x.tolist())
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def lerp_score(value: float | None, bad: float, good: float, none_value: float | None = None) -> float:
    """استيفاء خطي إلى [0,1]: bad→0 وgood→1 (يعمل مع الاتجاهين)."""
    if value is None:
        value = none_value
    if value is None:
        return 0.0
    if good == bad:
        return 1.0
    return clamp((value - bad) / (good - bad), 0.0, 1.0)


def level_of(value: float | None, warn: float, crit: float, direction: str) -> str:
    """safe / warn / crit حسب العتبات. direction: higher (الأعلى أفضل) أو lower."""
    if value is None:
        return "safe"
    if direction == "higher":
        if value < crit:
            return "crit"
        if value < warn:
            return "warn"
        return "safe"
    if value > crit:
        return "crit"
    if value > warn:
        return "warn"
    return "safe"


SEVERITY = {"safe": 0, "warn": 1, "crit": 2}
LEVEL_AR = {"safe": "جيدة", "warn": "قريبة من الخطر", "crit": "في خطر"}


def worst(levels: list[str]) -> str:
    return max(levels, key=lambda l: SEVERITY[l]) if levels else "safe"
