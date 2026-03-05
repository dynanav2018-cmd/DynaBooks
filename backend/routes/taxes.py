"""Tax rates routes."""

from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from sqlalchemy import text

from python_accounting.models import Account, Tax

from backend.serializers import serialize_tax

bp = Blueprint("taxes", __name__, url_prefix="/api")


def _is_expense_account(session, account_id):
    """Check if the given account is an expense type (not Control)."""
    if not account_id:
        return False
    account = session.get(Account, account_id)
    return account and account.account_type != Account.AccountType.CONTROL


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
        if account_id and _is_expense_account(g.session, account_id):
            # Bypass python-accounting's Control-account validation
            # by inserting via raw SQL for expense-type taxes.
            now = datetime.now(timezone.utc)
            conn = g.session.connection()

            # Insert recyclable row first (Tax inherits from Recyclable)
            result = conn.execute(text("""
                INSERT INTO recyclable (created_at, updated_at, recycled_type)
                VALUES (:now, :now, 'Tax')
            """), {"now": now})
            tax_id = result.lastrowid

            conn.execute(text("""
                INSERT INTO tax (id, name, code, rate, account_id, entity_id)
                VALUES (:id, :name, :code, :rate, :account_id, :entity_id)
            """), {
                "id": tax_id, "name": name, "code": code,
                "rate": rate, "account_id": account_id,
                "entity_id": g.session.entity.id,
            })
            g.session.commit()

            tax = g.session.get(Tax, tax_id)
        else:
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

    new_account_id = data.get("account_id", tax.account_id)

    try:
        if new_account_id and _is_expense_account(g.session, new_account_id):
            # Update via raw SQL to bypass Control-account validation
            conn = g.session.connection()
            now = datetime.now(timezone.utc)
            conn.execute(text("""
                UPDATE tax SET
                    name = :name, code = :code, rate = :rate, account_id = :account_id
                WHERE id = :id
            """), {
                "id": tax_id,
                "name": data.get("name", tax.name),
                "code": data.get("code", tax.code),
                "rate": data.get("rate", float(tax.rate)),
                "account_id": new_account_id,
            })
            conn.execute(text("""
                UPDATE recyclable SET updated_at = :now WHERE id = :id
            """), {"id": tax_id, "now": now})
            g.session.commit()
            g.session.expire(tax)
        else:
            if "name" in data:
                tax.name = data["name"]
            if "code" in data:
                tax.code = data["code"]
            if "rate" in data:
                tax.rate = data["rate"]
            if "account_id" in data:
                tax.account_id = data["account_id"]
            g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    tax = g.session.get(Tax, tax_id)
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
