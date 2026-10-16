"""كل ملف في هذا المجلد يعرّف `bp` (Blueprint) ويُسجَّل تلقائياً."""
from __future__ import annotations

from flask import jsonify, request


def bad_request(message: str, code: int = 400):
    return jsonify(error="bad_request", message=message), code


def json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}
