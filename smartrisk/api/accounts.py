"""تسجيل الدخول والخروج والحساب."""
from __future__ import annotations

import sqlite3

from flask import Blueprint, current_app, jsonify, request, session

from .. import auth
from . import bad_request, json_body

bp = Blueprint("api_accounts", __name__, url_prefix="/api/auth")


def _public(user: dict) -> dict:
    return {"id": user["id"], "email": user.get("email", ""), "name": user.get("name", "")}


@bp.get("/me")
def me():
    u = auth.current_user()
    return jsonify(user=_public(u) if u else None, auth_required=current_app.config["AUTH_REQUIRED"])


@bp.post("/register")
def register():
    if not current_app.config["AUTH_REQUIRED"] or not current_app.config["ALLOW_REGISTRATION"]:
        return bad_request("التسجيل غير متاح.", 403)
    d = json_body()
    email = str(d.get("email", "")).strip().lower()
    name = str(d.get("name", "")).strip()[:60]
    pw = str(d.get("password", ""))
    if not auth.validate_email(email):
        return bad_request("البريد الإلكتروني غير صالح.")
    if len(pw) < 8:
        return bad_request("كلمة المرور يجب ألا تقل عن 8 أحرف.")
    if len(pw) > 128:
        return bad_request("كلمة المرور طويلة جداً.")
    try:
        uid = auth.create_user(email, name or email.split("@")[0], pw)
    except sqlite3.IntegrityError:
        return bad_request("هذا البريد مسجّل مسبقاً.", 409)
    session.clear()
    session["uid"] = uid
    auth.csrf_token()
    return jsonify(user={"id": uid, "email": email, "name": name or email.split("@")[0]}, csrf=session["csrf"]), 201


@bp.post("/login")
def login():
    d = json_body()
    email = str(d.get("email", "")).strip().lower()
    pw = str(d.get("password", ""))
    key = f"{request.remote_addr}:{email}"
    if auth.throttle(key):
        return bad_request("محاولات كثيرة. انتظر بضع دقائق ثم أعد المحاولة.", 429)
    user = auth.verify_user(email, pw)
    if not user:
        auth.record_attempt(key)
        return bad_request("البريد أو كلمة المرور غير صحيحة.", 401)
    auth.clear_attempts(key)
    session.clear()
    session["uid"] = user["id"]
    auth.csrf_token()
    return jsonify(user=_public(user), csrf=session["csrf"])


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True)
