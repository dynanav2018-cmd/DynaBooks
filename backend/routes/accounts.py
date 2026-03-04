"""Chart of Accounts routes."""

from decimal import Decimal

from flask import Blueprint, g, jsonify, request
from sqlalchemy import text

from python_accounting.models import Account

from backend.serializers import serialize_account

bp = Blueprint("accounts", __name__, url_prefix="/api")


def _parse_account_type(value):
    """Parse an account type from name (OPERATING_EXPENSE) or value (Operating Expense)."""
    try:
        return Account.AccountType(value)
    except ValueError:
        pass
    try:
        return Account.AccountType[value]
    except KeyError:
        return None


EXPENSE_TYPES = {
    Account.AccountType.DIRECT_EXPENSE,
    Account.AccountType.OPERATING_EXPENSE,
    Account.AccountType.OVERHEAD_EXPENSE,
    Account.AccountType.OTHER_EXPENSE,
}

REVENUE_TYPES = {
    Account.AccountType.OPERATING_REVENUE,
    Account.AccountType.NON_OPERATING_REVENUE,
}


@bp.route("/accounts", methods=["GET"])
def list_accounts():
    query = g.session.query(Account)

    account_type = request.args.get("type")
    if account_type:
        at = _parse_account_type(account_type)
        if at is None:
            return jsonify(error=f"Invalid account type: {account_type}"), 400
        query = query.filter(Account.account_type == at)

    category = request.args.get("category")
    if category == "expense":
        query = query.filter(Account.account_type.in_(EXPENSE_TYPES))
    elif category == "revenue":
        query = query.filter(Account.account_type.in_(REVENUE_TYPES))

    accounts = query.all()
    return jsonify([serialize_account(a) for a in accounts])


@bp.route("/accounts", methods=["POST"])
def create_account():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    name = data.get("name")
    account_type = data.get("account_type")
    currency_id = data.get("currency_id")

    if not name or not account_type:
        return jsonify(error="name and account_type are required"), 400

    at = _parse_account_type(account_type)
    if at is None:
        return jsonify(error=f"Invalid account type: {account_type}"), 400

    # Default currency to entity's currency
    if not currency_id:
        currency_id = g.session.entity.currency_id

    account_code = data.get("account_code")

    try:
        account = Account(
            name=name,
            account_type=at,
            currency_id=currency_id,
            entity_id=g.session.entity.id,
            description=data.get("description"),
        )
        if account_code:
            account.account_code = int(account_code)
        g.session.add(account)
        g.session.flush()
        # Ensure account_code persists even if the library overrode it
        if account_code and account.account_code != int(account_code):
            g.session.connection().execute(
                text("UPDATE account SET account_code = :code WHERE id = :id"),
                {"code": int(account_code), "id": account.id},
            )
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_account(account)), 201


@bp.route("/accounts/<int:account_id>/ledger", methods=["GET"])
def get_account_ledger(account_id):
    """Return all posted transactions for an account."""
    account = g.session.get(Account, account_id)
    if not account:
        return jsonify(error="Account not found"), 404

    try:
        stmt = account.statement(g.session, None, None, schedule=False)
    except Exception as e:
        return jsonify(error=str(e)), 400

    def _dec(v):
        return float(v) if isinstance(v, Decimal) else v

    entries = []
    for tx in stmt.get("transactions", []):
        entries.append({
            "id": tx.id,
            "transaction_no": tx.transaction_no,
            "transaction_type": tx.transaction_type.value
            if tx.transaction_type
            else None,
            "transaction_date": tx.transaction_date.isoformat()
            if tx.transaction_date
            else None,
            "narration": tx.narration,
            "debit": _dec(getattr(tx, "debit", 0)),
            "credit": _dec(getattr(tx, "credit", 0)),
            "balance": _dec(getattr(tx, "balance", 0)),
        })

    return jsonify({
        "account": serialize_account(account),
        "opening_balance": _dec(stmt.get("opening_balance", 0)),
        "closing_balance": _dec(stmt.get("closing_balance", 0)),
        "entries": entries,
    })


@bp.route("/accounts/<int:account_id>", methods=["PUT"])
def update_account(account_id):
    account = g.session.get(Account, account_id)
    if not account:
        return jsonify(error="Account not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    # ORM-safe updates
    if "name" in data:
        account.name = data["name"]
    if "description" in data:
        account.description = data["description"]

    # Direct SQL for fields the library validates/regenerates
    sql_sets = []
    sql_params = {"id": account_id}
    if "account_code" in data and data["account_code"] not in (None, ""):
        sql_sets.append("account_code = :code")
        sql_params["code"] = int(data["account_code"])
    if "account_type" in data:
        at = _parse_account_type(data["account_type"])
        if at is None:
            return jsonify(error=f"Invalid account type: {data['account_type']}"), 400
        sql_sets.append("account_type = :atype")
        sql_params["atype"] = at.name

    try:
        if sql_sets:
            g.session.connection().execute(
                text(f"UPDATE account SET {', '.join(sql_sets)} WHERE id = :id"),
                sql_params,
            )
        g.session.commit()
        # Refresh to pick up raw SQL changes
        g.session.expire(account)
        account = g.session.get(Account, account_id)
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_account(account))


@bp.route("/accounts/<int:account_id>", methods=["DELETE"])
def delete_account(account_id):
    account = g.session.get(Account, account_id)
    if not account:
        return jsonify(error="Account not found"), 404

    try:
        g.session.delete(account)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Account deleted"), 200
