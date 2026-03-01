"""Chart of Accounts routes."""

from flask import Blueprint, g, jsonify, request

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

    try:
        account = Account(
            name=name,
            account_type=at,
            currency_id=currency_id,
            entity_id=g.session.entity.id,
            description=data.get("description"),
        )
        g.session.add(account)
        g.session.flush()
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_account(account)), 201


@bp.route("/accounts/<int:account_id>", methods=["PUT"])
def update_account(account_id):
    account = g.session.get(Account, account_id)
    if not account:
        return jsonify(error="Account not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    if "name" in data:
        account.name = data["name"]
    if "description" in data:
        account.description = data["description"]

    try:
        g.session.commit()
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
