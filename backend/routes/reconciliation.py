"""Bank Reconciliation routes."""

from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, g, jsonify, request
from sqlalchemy import text

from python_accounting.models import Account

from backend.models.bank_reconciliation import BankReconciliation, ReconciliationItem

bp = Blueprint("reconciliation", __name__, url_prefix="/api")


def _serialize_reconciliation(rec):
    return {
        "id": rec.id,
        "account_id": rec.account_id,
        "period_year": rec.period_year,
        "period_month": rec.period_month,
        "statement_balance": float(rec.statement_balance) if rec.statement_balance else 0,
        "status": rec.status,
        "completed_at": rec.completed_at.isoformat() if rec.completed_at else None,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


def _get_ledger_entries(session, account_id, year, month):
    """Get all posted ledger entries for a bank account in a given month."""
    conn = session.connection()
    rows = conn.execute(text("""
        SELECT l.id, l.transaction_id, t.transaction_date, t.narration,
               t.transaction_no, l.amount, l.entry_type
        FROM ledger l
        JOIN "transaction" t ON l.transaction_id = t.id
        JOIN recyclable r ON l.id = r.id
        WHERE l.post_account_id = :account_id
          AND strftime('%Y', t.transaction_date) = :year
          AND strftime('%m', t.transaction_date) = :month
          AND r.deleted_at IS NULL
          AND r.destroyed_at IS NULL
        ORDER BY t.transaction_date, l.id
    """), {
        "account_id": account_id,
        "year": str(year),
        "month": str(month).zfill(2),
    }).fetchall()

    return [{
        "ledger_id": r[0],
        "transaction_id": r[1],
        "transaction_date": r[2].isoformat() if hasattr(r[2], 'isoformat') else str(r[2]),
        "narration": r[3],
        "transaction_no": r[4],
        "amount": float(r[5]) if r[5] else 0,
        "entry_type": r[6],
    } for r in rows]


@bp.route("/reconciliations", methods=["GET"])
def list_reconciliations():
    """List all reconciliations, optionally filtered by account_id."""
    query = g.session.query(BankReconciliation)
    account_id = request.args.get("account_id")
    if account_id:
        query = query.filter(BankReconciliation.account_id == int(account_id))
    recs = query.order_by(
        BankReconciliation.period_year.desc(),
        BankReconciliation.period_month.desc(),
    ).all()
    return jsonify([_serialize_reconciliation(r) for r in recs])


@bp.route("/reconciliations", methods=["POST"])
def create_reconciliation():
    """Create or resume a reconciliation for a bank account + month."""
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    account_id = data.get("account_id")
    period_year = data.get("period_year")
    period_month = data.get("period_month")

    if not all([account_id, period_year, period_month]):
        return jsonify(error="account_id, period_year, period_month required"), 400

    # Check if reconciliation already exists
    existing = (
        g.session.query(BankReconciliation)
        .filter(
            BankReconciliation.account_id == account_id,
            BankReconciliation.period_year == period_year,
            BankReconciliation.period_month == period_month,
        )
        .first()
    )
    if existing:
        return jsonify(_serialize_reconciliation(existing)), 200

    rec = BankReconciliation(
        account_id=account_id,
        period_year=period_year,
        period_month=period_month,
        statement_balance=Decimal(str(data.get("statement_balance", 0))),
    )
    g.session.add(rec)

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(_serialize_reconciliation(rec)), 201


@bp.route("/reconciliations/<int:rec_id>", methods=["GET"])
def get_reconciliation(rec_id):
    """Get reconciliation with ledger entries and cleared status."""
    rec = g.session.get(BankReconciliation, rec_id)
    if not rec:
        return jsonify(error="Reconciliation not found"), 404

    entries = _get_ledger_entries(g.session, rec.account_id, rec.period_year, rec.period_month)

    # Get cleared items
    cleared_items = (
        g.session.query(ReconciliationItem)
        .filter(
            ReconciliationItem.reconciliation_id == rec_id,
            ReconciliationItem.is_cleared == True,
        )
        .all()
    )
    cleared_ids = {item.ledger_id for item in cleared_items}

    # Mark entries as cleared
    for entry in entries:
        entry["is_cleared"] = entry["ledger_id"] in cleared_ids

    # Calculate totals
    cleared_total = sum(
        e["amount"] if e["entry_type"] == "D" else -e["amount"]
        for e in entries if e["is_cleared"]
    )
    uncleared_total = sum(
        e["amount"] if e["entry_type"] == "D" else -e["amount"]
        for e in entries if not e["is_cleared"]
    )

    result = _serialize_reconciliation(rec)
    result["entries"] = entries
    result["cleared_total"] = cleared_total
    result["uncleared_total"] = uncleared_total
    return jsonify(result)


@bp.route("/reconciliations/<int:rec_id>", methods=["PUT"])
def update_reconciliation(rec_id):
    """Update reconciliation: toggle cleared items, update statement balance."""
    rec = g.session.get(BankReconciliation, rec_id)
    if not rec:
        return jsonify(error="Reconciliation not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    if "statement_balance" in data:
        rec.statement_balance = Decimal(str(data["statement_balance"]))

    # Update cleared items
    cleared_ledger_ids = data.get("cleared_ledger_ids")
    if cleared_ledger_ids is not None:
        # Delete existing items
        conn = g.session.connection()
        conn.execute(
            text("DELETE FROM reconciliation_items WHERE reconciliation_id = :rid"),
            {"rid": rec_id},
        )
        # Insert new cleared items
        for lid in cleared_ledger_ids:
            item = ReconciliationItem(
                reconciliation_id=rec_id,
                ledger_id=lid,
                is_cleared=True,
            )
            g.session.add(item)

    # Complete reconciliation
    if data.get("complete", False):
        rec.status = "completed"
        rec.completed_at = datetime.now(timezone.utc)

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(_serialize_reconciliation(rec))


@bp.route("/reconciliations/<int:rec_id>", methods=["DELETE"])
def delete_reconciliation(rec_id):
    """Delete a draft reconciliation."""
    rec = g.session.get(BankReconciliation, rec_id)
    if not rec:
        return jsonify(error="Reconciliation not found"), 404
    if rec.status == "completed":
        return jsonify(error="Cannot delete a completed reconciliation"), 400

    try:
        conn = g.session.connection()
        conn.execute(
            text("DELETE FROM reconciliation_items WHERE reconciliation_id = :rid"),
            {"rid": rec_id},
        )
        g.session.delete(rec)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Reconciliation deleted"), 200
