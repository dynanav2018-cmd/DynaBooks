"""Supplier Bill routes."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Account, LineItem, Transaction
from python_accounting.transactions import SupplierBill

from backend.models.transaction_contact import TransactionContact
from backend.serializers import serialize_transaction

bp = Blueprint("bills", __name__, url_prefix="/api")


def _get_bills(session):
    return (
        session.query(SupplierBill)
        .filter(Transaction.transaction_type == Transaction.TransactionType.SUPPLIER_BILL)
        .all()
    )


@bp.route("/bills", methods=["GET"])
def list_bills():
    bills = _get_bills(g.session)
    return jsonify([serialize_transaction(b) for b in bills])


@bp.route("/bills/<int:bill_id>", methods=["GET"])
def get_bill(bill_id):
    bill = g.session.get(SupplierBill, bill_id)
    if not bill:
        return jsonify(error="Bill not found"), 404
    return jsonify(serialize_transaction(bill))


@bp.route("/bills", methods=["POST"])
def create_bill():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    narration = data.get("narration", "Supplier Bill")
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

    # Default to first PAYABLE account
    if not account_id:
        payable = g.session.query(Account).filter(
            Account.account_type == Account.AccountType.PAYABLE
        ).first()
        if not payable:
            return jsonify(error="No payable account found"), 400
        account_id = payable.id

    try:
        bill = SupplierBill(
            narration=narration,
            transaction_date=tx_date,
            account_id=account_id,
            entity_id=entity.id,
        )
        g.session.add(bill)
        g.session.flush()

        for li_data in line_items_data:
            line = LineItem(
                narration=li_data.get("narration", ""),
                account_id=li_data["account_id"],
                amount=Decimal(str(li_data["amount"])),
                quantity=Decimal(str(li_data.get("quantity", 1))),
                tax_id=li_data.get("tax_id"),
                entity_id=entity.id,
            )
            g.session.add(line)
            g.session.flush()
            bill.line_items.add(line)
            g.session.flush()

        contact_id = data.get("contact_id")
        if contact_id:
            tc = TransactionContact(
                transaction_id=bill.id, contact_id=contact_id
            )
            g.session.add(tc)

        if data.get("post", False):
            bill.post(g.session)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(bill)), 201


@bp.route("/bills/<int:bill_id>", methods=["PUT"])
def update_bill(bill_id):
    bill = g.session.get(SupplierBill, bill_id)
    if not bill:
        return jsonify(error="Bill not found"), 404

    if bill.is_posted:
        return jsonify(error="Cannot update a posted bill"), 400

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    if "narration" in data:
        bill.narration = data["narration"]
    if "reference" in data:
        bill.reference = data["reference"]

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(bill))


@bp.route("/bills/<int:bill_id>", methods=["DELETE"])
def delete_bill(bill_id):
    bill = g.session.get(SupplierBill, bill_id)
    if not bill:
        return jsonify(error="Bill not found"), 404

    if bill.is_posted:
        return jsonify(error="Cannot delete a posted bill"), 400

    try:
        g.session.delete(bill)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Bill deleted"), 200


@bp.route("/bills/<int:bill_id>/post", methods=["POST"])
def post_bill(bill_id):
    bill = g.session.get(SupplierBill, bill_id)
    if not bill:
        return jsonify(error="Bill not found"), 404

    if bill.is_posted:
        return jsonify(error="Bill is already posted"), 409

    try:
        bill.post(g.session)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(bill))
