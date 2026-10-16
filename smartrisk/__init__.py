"""SmartRisk — منصة إدارة المخاطر المالية للمشاريع الصغيرة (الجزائر).

الهيكل:
  core/      محرك الحسابات الصرف (لا يعرف Flask) + محلّلات تُسجَّل تلقائياً
  api/       واجهات JSON (كل ملف يعرّف bp ويُسجَّل تلقائياً)
  web/       صفحات HTML
  data/      ملفات بيانات قابلة للتعديل (ضرائب، مؤشرات، أوزان، قاموس، قوالب)
  static/    CSS (tokens/base/components/pages) وJS (modules/components/lib)
"""
from __future__ import annotations

import importlib
import pkgutil

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from . import auth, db


def _register_blueprints(app: Flask) -> None:
    for pkg_name in ("api", "web"):
        pkg = importlib.import_module(f"{__name__}.{pkg_name}")
        for m in pkgutil.iter_modules(pkg.__path__):
            mod = importlib.import_module(f"{pkg.__name__}.{m.name}")
            bp = getattr(mod, "bp", None)
            if bp is not None:
                app.register_blueprint(bp)


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    from config import Config
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db.init_app(app)
    _register_blueprints(app)

    @app.before_request
    def _csrf():
        if request.path.startswith("/api/") or request.method in ("POST", "PUT", "DELETE", "PATCH"):
            auth.check_csrf()

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(HTTPException)
    def _http_error(e: HTTPException):
        if request.path.startswith("/api/"):
            return jsonify(error=e.name, message=e.description), e.code
        return e

    @app.errorhandler(Exception)
    def _unhandled(e: Exception):
        app.logger.exception("unhandled error")
        if request.path.startswith("/api/"):
            return jsonify(error="server_error", message="حدث خطأ غير متوقع في الخادم."), 500
        return "حدث خطأ غير متوقع.", 500

    @app.cli.command("seed-demo")
    def seed_demo():  # pragma: no cover
        """ينشئ مستخدماً تجريبياً (demo@smartrisk.dz / demo12345) مع مشاريع نموذجية. للتطوير فقط."""
        from . import repo
        with app.app_context():
            try:
                uid = auth.create_user("demo@smartrisk.dz", "حساب تجريبي", "demo12345")
            except Exception:  # noqa: BLE001
                print("المستخدم موجود مسبقاً.")
                return
            for t in ("clothing-shop", "workshop", "fast-food"):
                repo.create_project(uid, repo.load_template(t))
            print("تم: demo@smartrisk.dz / demo12345")

    return app
