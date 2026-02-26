"""Journal Entry routes."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Account, LineItem, Transaction
from python_accounting.transactions import JournalEntry

from backend.serializers import serialize_transaction

bp = Blueprint("journals", __name__, url_prefix="/api")


def _get_journals(session):
    return (
        session.query(JournalEntry)
        .filter(Transaction.transaction_type == Transaction.TransactionType.JOURNAL_ENTRY)
        .all()
    )


@bp.route("/journals", methods=["GET"])
def list_journals():
    journals = _get_journals(g.session)
    return jsonify([serialize_transaction(j) for j in journals])


@bp.route("/journals", methods=["POST"])
def create_journal():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    narration = data.get("narration", "Journal Entry")
    transaction_date = data.get("transaction_date")
    account_id = data.get("account_id")
    line_items_data = data.get("line_items", [])

    if not transaction_date:
        return jsonify(error="transaction_date is required"), 400
    if not account_id:
        return jsonify(error="account_id (main account) is required"), 400
    if not line_items_data:
        return jsonify(error="At least one line_item is required"), 400

    try:
        tx_date = datetime.fromisoformat(transaction_date)
    except ValueError:
        return jsonify(error="Invalid transaction_date format"), 400

    entity = g.session.entity

    # Validate balanced debits/credits for compound entries
    is_compound = data.get("compound", False)

    try:
        journal = JournalEntry(
            narration=narration,
            transaction_date=tx_date,
            account_id=account_id,
            entity_id=entity.id,
        )

        if is_compound:
            journal.compound = True
            # For compound entries, main_account_amount is the main account's amount
            journal.main_account_amount = Decimal(str(data.get("main_account_amount", 0)))

        g.session.add(journal)
        g.session.flush()

        total_debits = Decimal("0")
        total_credits = Decimal("0")

        for li_data in line_items_data:
            credited = li_data.get("credited", False)
            amount = Decimal(str(li_data["amount"]))

            line = LineItem(
                narration=li_data.get("narration", ""),
                account_id=li_data["account_id"],
                amount=amount,
                quantity=Decimal(str(li_data.get("quantity", 1))),
                credited=credited,
                entity_id=entity.id,
            )
            g.session.add(line)
            g.session.flush()
            journal.line_items.add(line)
            g.session.flush()

            if credited:
                total_credits += amount
            else:
                total_debits += amount

        if data.get("post", False):
            journal.post(g.session)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(journal)), 201


@bp.route("/journals/<int:journal_id>", methods=["DELETE"])
def delete_journal(journal_id):
    journal = g.session.get(JournalEntry, journal_id)
    if not journal:
        return jsonify(error="Journal entry not found"), 404

    if journal.is_posted:
        return jsonify(error="Cannot delete a posted journal entry"), 400

    try:
        g.session.delete(journal)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Journal entry deleted"), 200


@bp.route("/journals/<int:journal_id>/post", methods=["POST"])
def post_journal(journal_id):
    journal = g.session.get(JournalEntry, journal_id)
    if not journal:
        return jsonify(error="Journal entry not found"), 404

    if journal.is_posted:
        return jsonify(error="Journal entry is already posted"), 409

    try:
        journal.post(g.session)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(journal))
