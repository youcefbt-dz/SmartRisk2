"""سجلّ المحلّلات: لإضافة تحليل جديد اكتب دالة في مجلد analysis/ وزيّنها بـ @analyzer.

    from smartrisk.core.registry import analyzer

    @analyzer("my_analysis", title="تحليلي")
    def my_analysis(ctx, params):
        return {"hello": ctx.project["name"]}

تظهر تلقائياً عبر الواجهة: POST /api/projects/<id>/analyze/my_analysis
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Callable

from .engine import forecast as fc_mod
from .engine import rules as rules_mod
from .engine import schema
from .util import jsonable


@dataclass
class AnalyzerInfo:
    name: str
    fn: Callable
    title: str
    description: str = ""


_REGISTRY: dict[str, AnalyzerInfo] = {}


def analyzer(name: str, title: str | None = None, description: str = ""):
    def deco(fn: Callable) -> Callable:
        _REGISTRY[name] = AnalyzerInfo(name, fn, title or name, description or (fn.__doc__ or "").strip())
        return fn
    return deco


class Context:
    """سياق تحليل واحد: يخزّن النتائج الوسيطة كي لا تُحسب مرتين."""

    def __init__(self, project: dict, warnings: list[str] | None = None):
        self.project = project
        self.warnings = warnings or []
        self.rules = rules_mod.tax_rules()
        self._memo: dict[str, Any] = {}

    def memo(self, key: str, fn: Callable[[], Any]) -> Any:
        if key not in self._memo:
            self._memo[key] = fn()
        return self._memo[key]

    @property
    def regime(self) -> str:
        return self.memo("regime", lambda: fc_mod.resolve_regime(self.project, self.rules))[0]

    @property
    def regime_notes(self) -> list[str]:
        return self.memo("regime", lambda: fc_mod.resolve_regime(self.project, self.rules))[1]

    def forecast(self, project: dict | None = None, shocks: fc_mod.Shocks | None = None) -> fc_mod.Forecast:
        """توقع حتمي للمشروع الأساسي (مخزّن) أو لنسخة معدّلة/مع صدمات (غير مخزّن)."""
        if project is None and shocks is None:
            return self.memo("base", lambda: fc_mod.run_forecast(self.project, None, self.regime, self.rules))
        proj = project or self.project
        return fc_mod.run_forecast(proj, shocks, self.regime, self.rules)

    def metrics(self) -> dict:
        from .analysis.metrics import compute_metrics
        return self.memo("metrics", lambda: compute_metrics(self))


def autodiscover() -> None:
    from . import analysis
    for m in pkgutil.iter_modules(analysis.__path__):
        importlib.import_module(f"{analysis.__name__}.{m.name}")


def available() -> list[dict]:
    autodiscover()
    return [{"name": i.name, "title": i.title, "description": i.description} for i in _REGISTRY.values()]


def run(name: str, raw_project: dict, params: dict | None = None) -> dict:
    autodiscover()
    info = _REGISTRY.get(name)
    if info is None:
        raise KeyError(name)
    project, warnings = schema.normalize(raw_project)
    ctx = Context(project, warnings)
    out = info.fn(ctx, params or {})
    return jsonable(out)
