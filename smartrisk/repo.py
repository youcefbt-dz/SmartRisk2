"""مستودع المشاريع: كل التعامل مع جدول projects هنا فقط."""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

from .core.engine import schema
from .core.engine.rules import DATA_DIR
from .core.registry import Context
from .core.util import jsonable, worst
from .db import get_db


# ------------------------------------------------------------------ قوالب
def list_templates() -> list[dict]:
    out = []
    for f in sorted((DATA_DIR / "templates").glob("*.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        meta = j.get("_meta", {})
        out.append({"id": f.stem, "title": meta.get("title", f.stem), "description": meta.get("description", ""),
                    "icon": meta.get("icon", "folder")})
    return out


def load_template(tid: str) -> dict | None:
    if not tid.replace("-", "").replace("_", "").isalnum():
        return None
    f = Path(DATA_DIR) / "templates" / f"{tid}.json"
    if not f.is_file():
        return None
    j = json.loads(f.read_text(encoding="utf-8"))
    j.pop("_meta", None)
    return j


# ------------------------------------------------------------------ لقطة سريعة (بدون محاكاة)
def quick_snapshot(project: dict) -> dict:
    try:
        ctx = Context(project)
        m = ctx.metrics()
        levels = []
        levels.append("crit" if m["cash_out_month"] else "safe")
        if m["revenue_y1"] > 0:
            levels.append("crit" if m["net_margin_y1"] < 0 else "warn" if m["net_margin_y1"] < 0.08 else "safe")
            mos = m["margin_of_safety"]
            if mos is not None:
                levels.append("crit" if mos < 0.1 else "warn" if mos < 0.25 else "safe")
        return jsonable({
            "level": worst(levels), "revenue_y1": m["revenue_y1"], "net_margin_y1": m["net_margin_y1"],
            "min_cash": m["min_cash"], "cash_out_month": m["cash_out_month"], "empty": m["revenue_y1"] <= 0,
        })
    except Exception:  # noqa: BLE001 — اللقطة تجميلية ولا يجب أن تمنع الحفظ
        return {}


# ------------------------------------------------------------------ CRUD
def _row_to_dict(row, with_data: bool = False) -> dict:
    d = {"id": row["id"], "name": row["name"], "created_at": row["created_at"], "updated_at": row["updated_at"],
         "snapshot": json.loads(row["snapshot"] or "{}")}
    if with_data:
        d["data"] = json.loads(row["data"])
    return d


def count_projects(user_id: int) -> int:
    return get_db().execute("SELECT COUNT(*) c FROM projects WHERE user_id=?", (user_id,)).fetchone()["c"]


def list_projects(user_id: int) -> list[dict]:
    rows = get_db().execute(
        "SELECT id,name,snapshot,created_at,updated_at FROM projects WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_project(user_id: int, pid: str) -> dict | None:
    row = get_db().execute("SELECT * FROM projects WHERE id=? AND user_id=?", (pid, user_id)).fetchone()
    return _row_to_dict(row, True) if row else None


def create_project(user_id: int, raw: dict) -> tuple[dict, list[str]]:
    data, warnings = schema.normalize(raw)
    pid = uuid.uuid4().hex[:12]
    get_db().execute(
        "INSERT INTO projects (id,user_id,name,data,snapshot) VALUES (?,?,?,?,?)",
        (pid, user_id, data["name"], json.dumps(data, ensure_ascii=False), json.dumps(quick_snapshot(data))),
    )
    get_db().commit()
    return get_project(user_id, pid), warnings  # type: ignore[return-value]


def update_project(user_id: int, pid: str, raw: dict) -> tuple[dict | None, list[str]]:
    if get_project(user_id, pid) is None:
        return None, []
    data, warnings = schema.normalize(raw)
    get_db().execute(
        "UPDATE projects SET name=?, data=?, snapshot=?, updated_at=datetime('now') WHERE id=? AND user_id=?",
        (data["name"], json.dumps(data, ensure_ascii=False), json.dumps(quick_snapshot(data)), pid, user_id),
    )
    get_db().commit()
    return get_project(user_id, pid), warnings


def delete_project(user_id: int, pid: str) -> bool:
    cur = get_db().execute("DELETE FROM projects WHERE id=? AND user_id=?", (pid, user_id))
    get_db().commit()
    return cur.rowcount > 0


def duplicate_project(user_id: int, pid: str) -> dict | None:
    src = get_project(user_id, pid)
    if not src:
        return None
    data = deepcopy(src["data"])
    data["name"] = (data["name"] + " (نسخة)")[:60]
    proj, _ = create_project(user_id, data)
    return proj
