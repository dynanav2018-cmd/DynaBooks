"""Client Invoice routes."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Account, LineItem, Tax, Transaction
from python_accounting.transactions import ClientInvoice

from backend.models.transaction_contact import TransactionContact
from backend.serializers import serialize_transaction

bp = Blueprint("invoices", __name__, url_prefix="/api")


def _get_invoices(session):
    return (
        session.query(ClientInvoice)
        .filter(Transaction.transaction_type == Transaction.TransactionType.CLIENT_INVOICE)
        .all()
    )


@bp.route("/invoices", methods=["GET"])
def list_invoices():
    invoices = _get_invoices(g.session)
    return jsonify([serialize_transaction(inv) for inv in invoices])


@bp.route("/invoices/<int:invoice_id>", methods=["GET"])
def get_invoice(invoice_id):
    invoice = g.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return jsonify(error="Invoice not found"), 404
    return jsonify(serialize_transaction(invoice))


@bp.route("/invoices", methods=["POST"])
def create_invoice():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    narration = data.get("narration", "Client Invoice")
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

    # Default to first RECEIVABLE account
    if not account_id:
        receivable = g.session.query(Account).filter(
            Account.account_type == Account.AccountType.RECEIVABLE
        ).first()
        if not receivable:
            return jsonify(error="No receivable account found"), 400
        account_id = receivable.id

    try:
        invoice = ClientInvoice(
            narration=narration,
            transaction_date=tx_date,
            account_id=account_id,
            entity_id=entity.id,
        )
        g.session.add(invoice)
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
            invoice.line_items.add(line)
            g.session.flush()

        # Link contact if provided
        contact_id = data.get("contact_id")
        if contact_id:
            tc = TransactionContact(
                transaction_id=invoice.id, contact_id=contact_id
            )
            g.session.add(tc)

        # Auto-post if requested
        if data.get("post", False):
            invoice.post(g.session)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(invoice)), 201


@bp.route("/invoices/<int:invoice_id>", methods=["PUT"])
def update_invoice(invoice_id):
    invoice = g.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return jsonify(error="Invoice not found"), 404

    if invoice.is_posted:
        return jsonify(error="Cannot update a posted invoice"), 400

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    if "narration" in data:
        invoice.narration = data["narration"]
    if "reference" in data:
        invoice.reference = data["reference"]

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(invoice))


@bp.route("/invoices/<int:invoice_id>", methods=["DELETE"])
def delete_invoice(invoice_id):
    invoice = g.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return jsonify(error="Invoice not found"), 404

    if invoice.is_posted:
        return jsonify(error="Cannot delete a posted invoice"), 400

    try:
        g.session.delete(invoice)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Invoice deleted"), 200


@bp.route("/invoices/<int:invoice_id>/post", methods=["POST"])
def post_invoice(invoice_id):
    invoice = g.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return jsonify(error="Invoice not found"), 404

    if invoice.is_posted:
        return jsonify(error="Invoice is already posted"), 409

    try:
        invoice.post(g.session)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(invoice))
