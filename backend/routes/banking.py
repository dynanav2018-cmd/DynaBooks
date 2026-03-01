"""Banking routes — Client Receipts and Supplier Payments."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Account, Assignment, LineItem, Transaction
from python_accounting.transactions import (
    ClientReceipt,
    JournalEntry,
    SupplierPayment,
)

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


@bp.route("/receipts/<int:receipt_id>", methods=["DELETE"])
def delete_receipt(receipt_id):
    """Delete an unposted receipt."""
    from sqlalchemy import text

    receipt = g.session.get(ClientReceipt, receipt_id)
    if not receipt:
        return jsonify(error="Receipt not found"), 404
    if receipt.is_posted:
        return jsonify(error="Cannot delete a posted receipt. Use void instead."), 400
    try:
        # Expunge the loaded receipt from the session first
        g.session.expunge(receipt)
        conn = g.session.connection()
        conn.execute(text("DELETE FROM line_item WHERE transaction_id = :id"), {"id": receipt_id})
        conn.execute(text('DELETE FROM "transaction" WHERE id = :id'), {"id": receipt_id})
        conn.execute(text("DELETE FROM recyclable WHERE id = :id"), {"id": receipt_id})
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400
    return jsonify(message="Receipt deleted"), 200


@bp.route("/receipts/<int:receipt_id>/void", methods=["POST"])
def void_receipt(receipt_id):
    """Void a posted receipt by creating a reversing JournalEntry."""
    receipt = g.session.get(ClientReceipt, receipt_id)
    if not receipt:
        return jsonify(error="Receipt not found"), 404
    if not receipt.is_posted:
        return jsonify(error="Receipt is not posted. Delete it instead."), 400

    entity = g.session.entity
    try:
        # Remove any assignments linked to this receipt
        assignments = (
            g.session.query(Assignment)
            .filter(Assignment.transaction_id == receipt.id)
            .all()
        )
        for asgn in assignments:
            g.session.delete(asgn)
        g.session.flush()

        # Get the bank account from the receipt's line items
        bank_line = list(receipt.line_items)[0]
        bank_account_id = bank_line.account_id
        receipt_amount = receipt.amount

        # Create reversing JournalEntry:
        # Original receipt: Debit Bank, Credit Receivable
        # Reversal: Debit Receivable (main, credited=False), Credit Bank (line item)
        void_date = receipt.transaction_date
        journal = JournalEntry(
            narration=f"Void: {receipt.transaction_no} - {receipt.narration}",
            transaction_date=void_date,
            account_id=receipt.account_id,
            entity_id=entity.id,
            credited=False,
        )
        g.session.add(journal)
        g.session.flush()

        line = LineItem(
            narration=f"Void {receipt.transaction_no}",
            account_id=bank_account_id,
            amount=receipt_amount,
            entity_id=entity.id,
        )
        g.session.add(line)
        g.session.flush()
        journal.line_items.add(line)
        g.session.flush()

        journal.post(g.session)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(
        message=f"Receipt {receipt.transaction_no} voided",
        voiding_entry=journal.transaction_no,
    )


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


@bp.route("/payments/<int:payment_id>", methods=["DELETE"])
def delete_payment(payment_id):
    """Delete an unposted payment."""
    from sqlalchemy import text

    payment = g.session.get(SupplierPayment, payment_id)
    if not payment:
        return jsonify(error="Payment not found"), 404
    if payment.is_posted:
        return jsonify(error="Cannot delete a posted payment. Use void instead."), 400
    try:
        g.session.expunge(payment)
        conn = g.session.connection()
        conn.execute(text("DELETE FROM line_item WHERE transaction_id = :id"), {"id": payment_id})
        conn.execute(text('DELETE FROM "transaction" WHERE id = :id'), {"id": payment_id})
        conn.execute(text("DELETE FROM recyclable WHERE id = :id"), {"id": payment_id})
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400
    return jsonify(message="Payment deleted"), 200


@bp.route("/payments/<int:payment_id>/void", methods=["POST"])
def void_payment(payment_id):
    """Void a posted payment by creating a reversing JournalEntry."""
    payment = g.session.get(SupplierPayment, payment_id)
    if not payment:
        return jsonify(error="Payment not found"), 404
    if not payment.is_posted:
        return jsonify(error="Payment is not posted. Delete it instead."), 400

    entity = g.session.entity
    try:
        # Remove any assignments linked to this payment
        assignments = (
            g.session.query(Assignment)
            .filter(Assignment.transaction_id == payment.id)
            .all()
        )
        for asgn in assignments:
            g.session.delete(asgn)
        g.session.flush()

        # Get the bank account from the payment's line items
        bank_line = list(payment.line_items)[0]
        bank_account_id = bank_line.account_id
        payment_amount = payment.amount

        # Create reversing JournalEntry:
        # Original payment: Debit Payable, Credit Bank
        # Reversal: Debit Bank (line item), Credit Payable (main, credited=True)
        void_date = payment.transaction_date
        journal = JournalEntry(
            narration=f"Void: {payment.transaction_no} - {payment.narration}",
            transaction_date=void_date,
            account_id=payment.account_id,
            entity_id=entity.id,
            credited=True,
        )
        g.session.add(journal)
        g.session.flush()

        line = LineItem(
            narration=f"Void {payment.transaction_no}",
            account_id=bank_account_id,
            amount=payment_amount,
            entity_id=entity.id,
            credited=False,
        )
        g.session.add(line)
        g.session.flush()
        journal.line_items.add(line)
        g.session.flush()

        journal.post(g.session)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(
        message=f"Payment {payment.transaction_no} voided",
        voiding_entry=journal.transaction_no,
    )
