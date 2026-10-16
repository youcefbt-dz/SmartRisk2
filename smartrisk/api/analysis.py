"""تشغيل المحلّلات: على مشروع محفوظ أو على مسودة (معاينة حيّة دون حفظ)."""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict

from flask import Blueprint, jsonify, request

from .. import repo
from ..auth import current_user, login_required
from ..core import registry
from . import bad_request, json_body

bp = Blueprint("api_analysis", __name__, url_prefix="/api")

_CACHE: OrderedDict[str, dict] = OrderedDict()
_CACHE_MAX = 200


def _key(name: str, project: dict, params: dict) -> str:
    blob = json.dumps([name, project, params], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()


def _run(name: str, project: dict, params: dict):
    k = _key(name, project, params)
    if k in _CACHE:
        _CACHE.move_to_end(k)
        return _CACHE[k]
    try:
        out = registry.run(name, project, params)
    except KeyError:
        return None
    _CACHE[k] = out
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return out


def _params() -> dict:
    p = dict(request.args)
    body = json_body()
    if isinstance(body.get("params"), dict):
        p.update(body["params"])
    out = {}
    for k, v in p.items():
        if isinstance(v, str):
            try:
                out[k] = float(v) if v.replace(".", "", 1).lstrip("-").isdigit() else v
            except ValueError:
                out[k] = v
        else:
            out[k] = v
    return out


@bp.get("/analyzers")
def analyzers():
    return jsonify(analyzers=registry.available())


@bp.route("/projects/<pid>/analyze/<name>", methods=["GET", "POST"])
@login_required
def analyze(pid, name):
    proj = repo.get_project(current_user()["id"], pid)  # type: ignore[index]
    if not proj:
        return bad_request("المشروع غير موجود.", 404)
    out = _run(name, proj["data"], _params())
    if out is None:
        return bad_request("محلّل غير معروف.", 404)
    return jsonify(out)


@bp.post("/preview/<name>")
@login_required
def preview(name):
    """معاينة حيّة على مسودة غير محفوظة."""
    d = json_body()
    if not isinstance(d.get("project"), dict):
        return bad_request("أرسل المشروع في الحقل project.")
    out = _run(name, d["project"], _params())
    if out is None:
        return bad_request("محلّل غير معروف.", 404)
    return jsonify(out)
