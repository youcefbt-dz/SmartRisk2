"""CRUD للمشاريع + استيراد وتصدير."""
from __future__ import annotations

import json

from flask import Blueprint, Response, current_app, jsonify

from .. import repo
from ..auth import current_user, login_required
from ..core.engine import schema
from . import bad_request, json_body

bp = Blueprint("api_projects", __name__, url_prefix="/api/projects")


def _uid() -> int:
    return current_user()["id"]  # type: ignore[index]


@bp.get("")
@login_required
def list_():
    return jsonify(projects=repo.list_projects(_uid()))


@bp.post("")
@login_required
def create():
    if repo.count_projects(_uid()) >= current_app.config["MAX_PROJECTS_PER_USER"]:
        return bad_request("بلغت الحد الأقصى لعدد المشاريع.", 403)
    d = json_body()
    raw = None
    if d.get("template"):
        raw = repo.load_template(str(d["template"]))
        if raw is None:
            return bad_request("القالب غير موجود.", 404)
        if d.get("name"):
            raw["name"] = str(d["name"])[:60]
    elif isinstance(d.get("data"), dict):
        raw = d["data"]
    else:
        raw = schema.default_project()
        if d.get("name"):
            raw["name"] = str(d["name"])[:60]
    proj, warnings = repo.create_project(_uid(), raw)
    return jsonify(project=proj, warnings=warnings), 201


@bp.post("/import")
@login_required
def import_():
    d = json_body()
    data = d.get("data") if isinstance(d.get("data"), dict) else d
    if not isinstance(data, dict) or "products" not in data:
        return bad_request("ملف المشروع غير صالح.")
    if repo.count_projects(_uid()) >= current_app.config["MAX_PROJECTS_PER_USER"]:
        return bad_request("بلغت الحد الأقصى لعدد المشاريع.", 403)
    proj, warnings = repo.create_project(_uid(), data)
    return jsonify(project=proj, warnings=warnings), 201


@bp.get("/<pid>")
@login_required
def get(pid):
    proj = repo.get_project(_uid(), pid)
    if not proj:
        return bad_request("المشروع غير موجود.", 404)
    _, warnings = schema.normalize(proj["data"])
    return jsonify(project=proj, warnings=warnings)


@bp.put("/<pid>")
@login_required
def update(pid):
    d = json_body()
    raw = d.get("data") if isinstance(d.get("data"), dict) else d
    proj, warnings = repo.update_project(_uid(), pid, raw)
    if not proj:
        return bad_request("المشروع غير موجود.", 404)
    return jsonify(project=proj, warnings=warnings)


@bp.delete("/<pid>")
@login_required
def delete(pid):
    if not repo.delete_project(_uid(), pid):
        return bad_request("المشروع غير موجود.", 404)
    return jsonify(ok=True)


@bp.post("/<pid>/duplicate")
@login_required
def duplicate(pid):
    if repo.count_projects(_uid()) >= current_app.config["MAX_PROJECTS_PER_USER"]:
        return bad_request("بلغت الحد الأقصى لعدد المشاريع.", 403)
    proj = repo.duplicate_project(_uid(), pid)
    if not proj:
        return bad_request("المشروع غير موجود.", 404)
    return jsonify(project=proj), 201


@bp.get("/<pid>/export.json")
@login_required
def export_json(pid):
    proj = repo.get_project(_uid(), pid)
    if not proj:
        return bad_request("المشروع غير موجود.", 404)
    body = json.dumps(proj["data"], ensure_ascii=False, indent=2)
    return Response(body, mimetype="application/json", headers={
        "Content-Disposition": f"attachment; filename=smartrisk-{pid}.json"})
