"""Tax rates routes."""

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Tax

from backend.serializers import serialize_tax

bp = Blueprint("taxes", __name__, url_prefix="/api")


@bp.route("/taxes", methods=["GET"])
def list_taxes():
    taxes = g.session.query(Tax).all()
    return jsonify([serialize_tax(t) for t in taxes])


@bp.route("/taxes", methods=["POST"])
def create_tax():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    name = data.get("name")
    code = data.get("code")
    rate = data.get("rate")
    account_id = data.get("account_id")

    if not name or not code or rate is None:
        return jsonify(error="name, code, and rate are required"), 400

    try:
        tax = Tax(
            name=name,
            code=code,
            rate=rate,
            account_id=account_id,
            entity_id=g.session.entity.id,
        )
        g.session.add(tax)
        g.session.flush()
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_tax(tax)), 201


@bp.route("/taxes/<int:tax_id>", methods=["PUT"])
def update_tax(tax_id):
    tax = g.session.get(Tax, tax_id)
    if not tax:
        return jsonify(error="Tax not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    if "name" in data:
        tax.name = data["name"]
    if "code" in data:
        tax.code = data["code"]
    if "rate" in data:
        tax.rate = data["rate"]
    if "account_id" in data:
        tax.account_id = data["account_id"]

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_tax(tax))


@bp.route("/taxes/<int:tax_id>", methods=["DELETE"])
def delete_tax(tax_id):
    tax = g.session.get(Tax, tax_id)
    if not tax:
        return jsonify(error="Tax not found"), 404

    try:
        g.session.delete(tax)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Tax deleted"), 200
