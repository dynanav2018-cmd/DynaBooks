"""Recurring journal entry template routes."""

import json

from flask import Blueprint, g, jsonify, request

from backend.models.recurring_journal import RecurringJournal
from backend.serializers import serialize_recurring_journal

bp = Blueprint("recurring_journals", __name__, url_prefix="/api")


@bp.route("/recurring-journals", methods=["GET"])
def list_recurring_journals():
    """List all active recurring journal templates."""
    query = g.session.query(RecurringJournal).filter(
        RecurringJournal.is_active == True
    )
    templates = query.all()
    return jsonify([serialize_recurring_journal(t) for t in templates])


@bp.route("/recurring-journals", methods=["POST"])
def create_recurring_journal():
    """Create a new recurring journal template."""
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    name = data.get("name")
    if not name:
        return jsonify(error="name is required"), 400

    account_id = data.get("account_id")

    line_items = data.get("line_items")
    if not line_items or not isinstance(line_items, list):
        return jsonify(error="line_items array is required"), 400

    rj = RecurringJournal(
        name=name,
        narration=data.get("narration"),
        account_id=int(account_id) if account_id else None,
        line_items_json=json.dumps(line_items),
    )
    g.session.add(rj)

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_recurring_journal(rj)), 201


@bp.route("/recurring-journals/<int:rj_id>", methods=["PUT"])
def update_recurring_journal(rj_id):
    """Update a recurring journal template."""
    rj = g.session.get(RecurringJournal, rj_id)
    if not rj:
        return jsonify(error="Template not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    if "name" in data:
        rj.name = data["name"]
    if "narration" in data:
        rj.narration = data["narration"]
    if "account_id" in data:
        rj.account_id = int(data["account_id"])
    if "line_items" in data:
        rj.line_items_json = json.dumps(data["line_items"])

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_recurring_journal(rj))


@bp.route("/recurring-journals/<int:rj_id>", methods=["DELETE"])
def delete_recurring_journal(rj_id):
    """Soft-delete a recurring journal template."""
    rj = g.session.get(RecurringJournal, rj_id)
    if not rj:
        return jsonify(error="Template not found"), 404

    rj.is_active = False

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Template deactivated"), 200
