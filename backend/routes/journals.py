"""Journal Entry routes."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request
from sqlalchemy import text

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


def _derive_main_account(line_items_data: list) -> tuple:
    """Pick one line item to serve as the JournalEntry main account.

    The python-accounting library requires every transaction to have an
    ``account_id`` (main account) that is distinct from all line-item
    accounts.  This helper picks the best candidate from the user-supplied
    lines, removes it from the list, and returns the info needed to create
    the JournalEntry in compound mode.

    Returns:
        (account_id, credited, amount, remaining_items)
    """
    if not line_items_data or len(line_items_data) < 2:
        return None, False, Decimal("0"), line_items_data

    # Count how many times each account_id appears across lines.
    account_counts: dict[int, int] = {}
    for li in line_items_data:
        aid = li["account_id"]
        account_counts[aid] = account_counts.get(aid, 0) + 1

    # Prefer the first line whose account is unique (appears only once)
    # so that no remaining line item will conflict with the main account.
    best_idx = 0
    for i, li in enumerate(line_items_data):
        if account_counts[li["account_id"]] == 1:
            best_idx = i
            break

    main_line = line_items_data[best_idx]
    remaining = [li for j, li in enumerate(line_items_data) if j != best_idx]

    return (
        main_line["account_id"],
        main_line.get("credited", False),
        Decimal(str(main_line.get("amount", 0))),
        remaining,
    )


@bp.route("/journals", methods=["GET"])
def list_journals():
    journals = _get_journals(g.session)
    return jsonify([serialize_transaction(j) for j in journals])


@bp.route("/journals/<int:journal_id>", methods=["GET"])
def get_journal(journal_id):
    journal = g.session.get(JournalEntry, journal_id)
    if not journal:
        return jsonify(error="Journal entry not found"), 404
    return jsonify(serialize_transaction(journal))


@bp.route("/journals/<int:journal_id>", methods=["PUT"])
def update_journal(journal_id):
    journal = g.session.get(JournalEntry, journal_id)
    if not journal:
        return jsonify(error="Journal entry not found"), 404

    if journal.is_posted:
        return jsonify(error="Cannot update a posted journal entry"), 400

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    # Update basic fields
    if "narration" in data:
        journal.narration = data["narration"]
    if "transaction_date" in data:
        try:
            journal.transaction_date = datetime.fromisoformat(
                data["transaction_date"]
            )
        except ValueError:
            return jsonify(error="Invalid transaction_date format"), 400

    try:
        line_items_data = data.get("line_items")
        if line_items_data is not None:
            # Delete existing line items via raw SQL
            conn = g.session.connection()
            conn.execute(
                text("DELETE FROM line_item WHERE transaction_id = :tid"),
                {"tid": journal_id},
            )
            g.session.flush()

            # Re-derive the main account from the new line items
            account_id, main_credited, main_amount, remaining = (
                _derive_main_account(line_items_data)
            )
            if not account_id:
                return jsonify(
                    error="Could not derive main account from line items"
                ), 400

            journal.account_id = account_id
            journal.credited = main_credited
            journal.compound = True
            journal.main_account_amount = main_amount

            entity = g.session.entity

            # Recreate line items
            for li_data in remaining:
                line = LineItem(
                    narration=li_data.get("narration", ""),
                    account_id=li_data["account_id"],
                    amount=Decimal(str(li_data["amount"])),
                    quantity=Decimal(str(li_data.get("quantity", 1))),
                    credited=li_data.get("credited", False),
                    entity_id=entity.id,
                    transaction_id=journal_id,
                )
                g.session.add(line)
                g.session.flush()

            # Expire to pick up new line_items on next access
            g.session.expire(journal)

        # Auto-post if requested
        if data.get("post", False):
            journal.post(g.session)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(journal))


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
    if not line_items_data:
        return jsonify(error="At least one line_item is required"), 400

    try:
        tx_date = datetime.fromisoformat(transaction_date)
    except ValueError:
        return jsonify(error="Invalid transaction_date format"), 400

    entity = g.session.entity

    # When no explicit main account is provided, auto-derive one from the
    # line items and use compound mode so each line's credited flag is
    # respected individually.
    if not account_id:
        if len(line_items_data) < 2:
            return jsonify(error="At least two line items are required"), 400
        account_id, main_credited, main_amount, line_items_data = \
            _derive_main_account(line_items_data)
        if not account_id:
            return jsonify(
                error="Could not derive main account from line items"
            ), 400
        use_compound = True
    else:
        # Backward-compatible path: explicit account_id provided.
        main_credited = True  # JournalEntry default
        main_amount = None
        use_compound = data.get("compound", False)

    try:
        journal = JournalEntry(
            narration=narration,
            transaction_date=tx_date,
            account_id=account_id,
            entity_id=entity.id,
            credited=main_credited,
        )

        if use_compound:
            journal.compound = True
            if main_amount is not None:
                journal.main_account_amount = main_amount
            else:
                journal.main_account_amount = Decimal(
                    str(data.get("main_account_amount", 0))
                )

        g.session.add(journal)
        g.session.flush()

        # Persist all LineItems first, then batch-add them to the
        # journal relationship in one go.  This avoids intermediate
        # flushes that trigger the library's compound-balance
        # validation before all lines are present.
        persisted_lines = []
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
            persisted_lines.append(line)

        for line in persisted_lines:
            journal.line_items.add(line)
        g.session.flush()

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
