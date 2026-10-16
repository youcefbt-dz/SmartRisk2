"""بيانات مرجعية للواجهة: القاموس، القوالب، القواعد، الخيارات."""
from __future__ import annotations

from flask import Blueprint, jsonify

from .. import repo
from ..core.engine import rules, schema

bp = Blueprint("api_meta", __name__, url_prefix="/api/meta")


@bp.get("/glossary")
def glossary():
    return jsonify(terms=rules.glossary())


@bp.get("/templates")
def templates():
    return jsonify(templates=repo.list_templates())


@bp.get("/rules")
def rules_():
    return jsonify(tax=rules.tax_rules(), funding=rules.funding_programs(),
                   scoring=rules.scoring_def(), kri=rules.kri_defs())


@bp.get("/options")
def options():
    return jsonify(sectors=schema.SECTORS, legal_forms=schema.LEGAL_FORMS, activities=schema.ACTIVITIES,
                   regimes=schema.REGIMES, defaults=schema.default_project())
