"""Banking routes — Client Receipts and Supplier Payments."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Account, LineItem, Transaction
from python_accounting.transactions import ClientReceipt, SupplierPayment

from backend.serializers import serialize_transaction

bp = Blueprint("banking", __name__, url_prefix="/api")


# ── Client Receipts ─────────────────────────────────────────────────

@bp.route("/receipts", methods=["GET"])
def list_receipts():
    receipts = (
        g.session.query(ClientReceipt)
        .filter(Transaction.transaction_type == Transaction.TransactionType.CLIENT_RECEIPT)
        .all()
    )
    return jsonify([serialize_transaction(r) for r in receipts])


@bp.route("/receipts", methods=["POST"])
def create_receipt():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    narration = data.get("narration", "Client Receipt")
    transaction_date = data.get("transaction_date")
    account_id = data.get("account_id")
    line_items_data = data.get("line_items", [])

    if not transaction_date:
        return jsonify(error="transaction_date is required"), 400
    if not line_items_data:
        return jsonify(error="At least one line_item is required"), 400

    try:
        tx_date = datetime.fromisoformat(transaction_date)
    except ValueError:
        return jsonify(error="Invalid transaction_date format"), 400

    entity = g.session.entity

    # Default to RECEIVABLE account
    if not account_id:
        receivable = g.session.query(Account).filter(
            Account.account_type == Account.AccountType.RECEIVABLE
        ).first()
        if not receivable:
            return jsonify(error="No receivable account found"), 400
        account_id = receivable.id

    try:
        receipt = ClientReceipt(
            narration=narration,
            transaction_date=tx_date,
            account_id=account_id,
            entity_id=entity.id,
        )
        g.session.add(receipt)
        g.session.flush()

        for li_data in line_items_data:
            line = LineItem(
                narration=li_data.get("narration", ""),
                account_id=li_data["account_id"],
                amount=Decimal(str(li_data["amount"])),
                entity_id=entity.id,
            )
            g.session.add(line)
            g.session.flush()
            receipt.line_items.add(line)
            g.session.flush()

        if data.get("post", False):
            receipt.post(g.session)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(receipt)), 201


# ── Supplier Payments ───────────────────────────────────────────────

@bp.route("/payments", methods=["GET"])
def list_payments():
    payments = (
        g.session.query(SupplierPayment)
        .filter(Transaction.transaction_type == Transaction.TransactionType.SUPPLIER_PAYMENT)
        .all()
    )
    return jsonify([serialize_transaction(p) for p in payments])


@bp.route("/payments", methods=["POST"])
def create_payment():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    narration = data.get("narration", "Supplier Payment")
    transaction_date = data.get("transaction_date")
    account_id = data.get("account_id")
    line_items_data = data.get("line_items", [])

    if not transaction_date:
        return jsonify(error="transaction_date is required"), 400
    if not line_items_data:
        return jsonify(error="At least one line_item is required"), 400

    try:
        tx_date = datetime.fromisoformat(transaction_date)
    except ValueError:
        return jsonify(error="Invalid transaction_date format"), 400

    entity = g.session.entity

    # Default to PAYABLE account
    if not account_id:
        payable = g.session.query(Account).filter(
            Account.account_type == Account.AccountType.PAYABLE
        ).first()
        if not payable:
            return jsonify(error="No payable account found"), 400
        account_id = payable.id

    try:
        payment = SupplierPayment(
            narration=narration,
            transaction_date=tx_date,
            account_id=account_id,
            entity_id=entity.id,
        )
        g.session.add(payment)
        g.session.flush()

        for li_data in line_items_data:
            line = LineItem(
                narration=li_data.get("narration", ""),
                account_id=li_data["account_id"],
                amount=Decimal(str(li_data["amount"])),
                entity_id=entity.id,
            )
            g.session.add(line)
            g.session.flush()
            payment.line_items.add(line)
            g.session.flush()

        if data.get("post", False):
            payment.post(g.session)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(payment)), 201
