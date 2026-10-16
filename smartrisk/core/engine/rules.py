"""تحميل ملفات البيانات القابلة للتعديل (ضرائب، مؤشرات، أوزان، برامج تمويل، قاموس)."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(os.environ.get("SMARTRISK_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))


def _load(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def tax_rules() -> dict:
    return _load("tax_rules.json")


@lru_cache(maxsize=None)
def kri_defs() -> list:
    return _load("kri.json")


@lru_cache(maxsize=None)
def scoring_def() -> dict:
    return _load("scoring.json")


@lru_cache(maxsize=None)
def funding_programs() -> dict:
    return _load("funding_programs.json")


@lru_cache(maxsize=None)
def glossary() -> list:
    return _load("glossary.json")


def reload_all() -> None:
    for fn in (tax_rules, kri_defs, scoring_def, funding_programs, glossary):
        fn.cache_clear()


def ibs_rate_for(project: dict) -> float:
    """نسبة IBS المطبّقة بحسب قطاع المشروع إلا إذا حدّد المستخدم نسبة يدوية."""
    custom = project.get("tax", {}).get("ibs_rate")
    if custom is not None:
        return float(custom)
    r = tax_rules()
    key = r["sector_ibs_map"].get(project.get("sector", "commerce"), "other")
    return float(r["ibs"][key])
