"""Assignment routes — link receipts to invoices, payments to bills."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Assignment

from backend.serializers import serialize_assignment

bp = Blueprint("assignments", __name__, url_prefix="/api")


@bp.route("/assignments", methods=["POST"])
def create_assignment():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    transaction_id = data.get("transaction_id")
    assigned_id = data.get("assigned_id")
    assigned_type = data.get("assigned_type")
    amount = data.get("amount")
    assignment_date = data.get("assignment_date")

    if not all([transaction_id, assigned_id, assigned_type, amount]):
        return jsonify(
            error="transaction_id, assigned_id, assigned_type, and amount are required"
        ), 400

    if not assignment_date:
        assignment_date = datetime.now().isoformat()

    try:
        asgn_date = datetime.fromisoformat(assignment_date)
    except ValueError:
        return jsonify(error="Invalid assignment_date format"), 400

    try:
        assignment = Assignment(
            assignment_date=asgn_date,
            transaction_id=transaction_id,
            assigned_id=assigned_id,
            assigned_type=assigned_type,
            amount=Decimal(str(amount)),
            entity_id=g.session.entity.id,
        )
        g.session.add(assignment)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_assignment(assignment)), 201
