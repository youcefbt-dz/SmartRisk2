"""مسارات الصفحات. لإضافة صفحة جديدة: أضف مساراً هنا وقالباً في templates/pages/."""
from __future__ import annotations

import json

from flask import Blueprint, abort, current_app, redirect, render_template, url_for

from .. import repo
from ..auth import csrf_token, current_user, login_required
from ..core.engine import schema

bp = Blueprint("web", __name__)

# عناصر القائمة العلوية. لإضافة رابط أضف عنصراً هنا فقط.
NAV_PUBLIC = [
    {"endpoint": "web.landing", "label": "الرئيسية"},
    {"endpoint": "web.guide", "label": "الدليل والمنهجية"},
]


def _boot(extra: dict | None = None) -> str:
    u = current_user()
    data = {
        "csrf": csrf_token(),
        "user": {"name": u["name"], "email": u.get("email", ""), "local": bool(u.get("local"))} if u else None,
        "authRequired": current_app.config["AUTH_REQUIRED"],
        "options": {"sectors": schema.SECTORS, "legalForms": schema.LEGAL_FORMS, "activities": schema.ACTIVITIES,
                    "regimes": schema.REGIMES},
    }
    if extra:
        data.update(extra)
    # حماية من إغلاق وسم script داخل JSON
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


@bp.app_context_processor
def inject():
    return {"nav_public": NAV_PUBLIC, "user": current_user()}


def render(template: str, page: str, **kw):
    return render_template(template, page=page, boot=_boot(kw.pop("boot_extra", None)), **kw)


@bp.get("/")
def landing():
    return render("pages/landing.html", "landing")


@bp.get("/guide")
def guide():
    return render("pages/guide.html", "guide")


@bp.get("/login")
def login():
    if current_user() and current_app.config["AUTH_REQUIRED"]:
        return redirect(url_for("web.projects"))
    return render("pages/login.html", "login", mode="login")


@bp.get("/register")
def register():
    if not current_app.config["ALLOW_REGISTRATION"] or not current_app.config["AUTH_REQUIRED"]:
        return redirect(url_for("web.login"))
    return render("pages/login.html", "register", mode="register")


@bp.get("/app")
@login_required
def projects():
    return render("pages/projects.html", "projects")


@bp.get("/app/p/<pid>")
@login_required
def workspace(pid):
    proj = repo.get_project(current_user()["id"], pid)  # type: ignore[index]
    if not proj:
        abort(404)
    return render("pages/workspace.html", "workspace", project_name=proj["name"],
                  boot_extra={"projectId": pid})


@bp.get("/app/p/<pid>/report")
@login_required
def report(pid):
    proj = repo.get_project(current_user()["id"], pid)  # type: ignore[index]
    if not proj:
        abort(404)
    return render("pages/report.html", "report", project_name=proj["name"], boot_extra={"projectId": pid})


@bp.app_errorhandler(404)
def not_found(_e):
    from flask import request
    if request.path.startswith("/api/"):
        return {"error": "not_found", "message": "غير موجود."}, 404
    return render_template("pages/error.html", page="error", boot=_boot(), code=404, title="الصفحة غير موجودة",
                           text="الرابط الذي فتحته غير صحيح أو أن المشروع حُذف."), 404
