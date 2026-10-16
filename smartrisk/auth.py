"""المصادقة: جلسات Flask + تجزئة كلمات المرور + حماية CSRF + تحديد محاولات الدخول."""
from __future__ import annotations

import hmac
import re
import secrets
import time
from functools import wraps

from flask import abort, current_app, g, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
_attempts: dict[str, list[float]] = {}
WINDOW, MAX_ATTEMPTS = 300, 8
LOCAL_EMAIL = "local@smartrisk.local"


# ------------------------------------------------------------------ المستخدم الحالي
def _ensure_local_user() -> int:
    db = get_db()
    row = db.execute("SELECT id FROM users WHERE email=?", (LOCAL_EMAIL,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO users (email, name, password_hash) VALUES (?,?,?)",
                     (LOCAL_EMAIL, "المستخدم المحلي", generate_password_hash(secrets.token_hex(16))))
    db.commit()
    return cur.lastrowid


def current_user() -> dict | None:
    if "user" in g:
        return g.user
    user = None
    if not current_app.config["AUTH_REQUIRED"]:
        uid = _ensure_local_user()
        user = {"id": uid, "email": "", "name": "المستخدم المحلي", "local": True}
    else:
        uid = session.get("uid")
        if uid:
            row = get_db().execute("SELECT id, email, name FROM users WHERE id=?", (uid,)).fetchone()
            if row:
                user = dict(row)
    g.user = user
    return user


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if current_user() is None:
            if request.path.startswith("/api/"):
                return jsonify(error="unauthorized", message="سجّل الدخول أولاً."), 401
            return redirect(url_for("web.login", next=request.path))
        return view(*a, **kw)
    return wrapped


# ------------------------------------------------------------------ CSRF
def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf() -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    sent = request.headers.get("X-CSRF-Token", "")
    if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
        abort(403, description="رمز الحماية غير صالح. أعد تحميل الصفحة.")


# ------------------------------------------------------------------ تحديد المحاولات
def throttle(key: str) -> bool:
    """True إذا تجاوز المفتاح الحد المسموح."""
    now = time.time()
    hits = [t for t in _attempts.get(key, []) if now - t < WINDOW]
    _attempts[key] = hits
    return len(hits) >= MAX_ATTEMPTS


def record_attempt(key: str) -> None:
    _attempts.setdefault(key, []).append(time.time())


def clear_attempts(key: str) -> None:
    _attempts.pop(key, None)


# ------------------------------------------------------------------ عمليات الحساب
def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def create_user(email: str, name: str, password: str) -> int:
    cur = get_db().execute("INSERT INTO users (email, name, password_hash) VALUES (?,?,?)",
                           (email, name, generate_password_hash(password)))
    get_db().commit()
    return cur.lastrowid


def verify_user(email: str, password: str) -> dict | None:
    row = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    # مقارنة وهمية لتثبيت زمن الاستجابة عند غياب المستخدم
    if row is None:
        check_password_hash(generate_password_hash("x"), password)
        return None
    return dict(row) if check_password_hash(row["password_hash"], password) else None
