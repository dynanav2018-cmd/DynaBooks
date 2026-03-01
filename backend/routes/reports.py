"""Financial Reports routes."""

from datetime import datetime

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Account, Transaction
from python_accounting.reports import (
    IncomeStatement,
    BalanceSheet,
    TrialBalance,
    CashflowStatement,
    AgingSchedule,
)

from backend.models.contact import Contact
from backend.models.transaction_contact import TransactionContact
from backend.serializers import serialize_report_section, _dec

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _parse_date(param_name):
    """Parse a date from query string, return (datetime, error_response)."""
    value = request.args.get(param_name)
    if not value:
        return None, None
    try:
        return datetime.fromisoformat(value), None
    except ValueError:
        return None, (jsonify(error=f"Invalid {param_name} format"), 400)


@bp.route("/income-statement", methods=["GET"])
def income_statement():
    start_date, err = _parse_date("from")
    if err:
        return err
    end_date, err = _parse_date("to")
    if err:
        return err

    try:
        report = IncomeStatement(g.session, start_date, end_date)
        result = serialize_report_section(
            report.balances, report.accounts, report.totals, report.result_amounts
        )
    except Exception as e:
        return jsonify(error=str(e)), 400

    return jsonify(result)


@bp.route("/balance-sheet", methods=["GET"])
def balance_sheet():
    as_of, err = _parse_date("as_of")
    if err:
        return err

    try:
        report = BalanceSheet(g.session, as_of)
        result = serialize_report_section(
            report.balances, report.accounts, report.totals, report.result_amounts
        )
    except Exception as e:
        return jsonify(error=str(e)), 400

    return jsonify(result)


@bp.route("/trial-balance", methods=["GET"])
def trial_balance():
    as_of, err = _parse_date("as_of")
    if err:
        return err

    try:
        report = TrialBalance(g.session, as_of)
        result = serialize_report_section(
            report.balances, None, None, report.result_amounts
        )
    except Exception as e:
        return jsonify(error=str(e)), 400

    return jsonify(result)


@bp.route("/cashflow", methods=["GET"])
def cashflow():
    start_date, err = _parse_date("from")
    if err:
        return err
    end_date, err = _parse_date("to")
    if err:
        return err

    try:
        report = CashflowStatement(g.session, start_date, end_date)
        result = serialize_report_section(
            report.balances, None, None, report.result_amounts
        )
    except Exception as e:
        return jsonify(error=str(e)), 400

    return jsonify(result)


@bp.route("/aging-receivables", methods=["GET"])
def aging_receivables():
    as_of, err = _parse_date("as_of")
    if err:
        return err

    try:
        report = AgingSchedule(
            g.session, Account.AccountType.RECEIVABLE, as_of
        )
        result = {
            "balances": {k: _dec(v) for k, v in report.balances.items()},
            "accounts": [
                {
                    "id": a.id,
                    "name": a.name,
                    "balances": {k: _dec(v) for k, v in a.balances.items()}
                    if hasattr(a, "balances") and a.balances
                    else {},
                }
                for a in report.accounts
            ],
        }
    except Exception as e:
        return jsonify(error=str(e)), 400

    return jsonify(result)


@bp.route("/aging-payables", methods=["GET"])
def aging_payables():
    as_of, err = _parse_date("as_of")
    if err:
        return err

    try:
        report = AgingSchedule(
            g.session, Account.AccountType.PAYABLE, as_of
        )
        result = {
            "balances": {k: _dec(v) for k, v in report.balances.items()},
            "accounts": [
                {
                    "id": a.id,
                    "name": a.name,
                    "balances": {k: _dec(v) for k, v in a.balances.items()}
                    if hasattr(a, "balances") and a.balances
                    else {},
                }
                for a in report.accounts
            ],
        }
    except Exception as e:
        return jsonify(error=str(e)), 400

    return jsonify(result)


# ── Detailed Aging Reports ────────────────────────────────────────

_AGE_BRACKETS = [
    (0, 30, "Current"),
    (31, 90, "31-90 Days"),
    (91, 180, "91-180 Days"),
    (181, 365, "181-365 Days"),
    (366, None, "365+ Days"),
]


def _age_bracket(days):
    """Return the aging bracket label for a given number of days."""
    for lo, hi, label in _AGE_BRACKETS:
        if hi is None or days <= hi:
            if days >= lo:
                return label
    return "365+ Days"


def _build_aging_detail(session, account_type, as_of):
    """Build per-contact aging detail for RECEIVABLE or PAYABLE accounts."""
    if as_of is None:
        as_of = datetime.now()

    accounts = (
        session.query(Account)
        .filter(
            Account.entity_id == session.entity.id,
            Account.account_type == account_type,
        )
        .all()
    )

    # Collect all outstanding transactions across matching accounts
    all_transactions = []
    for acct in accounts:
        stmt = acct.statement(session, None, as_of, schedule=True)
        for tx in stmt.get("transactions", []):
            uncleared = getattr(tx, "uncleared_amount", None)
            if uncleared and uncleared > 0:
                all_transactions.append(tx)

    # Look up contacts for each transaction
    tx_ids = [tx.id for tx in all_transactions]
    contact_map = {}  # transaction_id -> contact
    if tx_ids:
        tcs = (
            session.query(TransactionContact, Contact)
            .join(Contact, Contact.id == TransactionContact.contact_id)
            .filter(TransactionContact.transaction_id.in_(tx_ids))
            .all()
        )
        for tc, contact in tcs:
            contact_map[tc.transaction_id] = contact

    # Group by contact
    contacts_dict = {}  # contact_id -> {info + transactions}
    unassigned_txs = []

    for tx in all_transactions:
        age_days = (as_of - tx.transaction_date).days
        bracket = _age_bracket(age_days)
        tx_data = {
            "transaction_no": tx.transaction_no,
            "transaction_date": tx.transaction_date.isoformat(),
            "amount": _dec(tx.amount),
            "outstanding": _dec(tx.uncleared_amount),
            "age_days": age_days,
            "age_bracket": bracket,
        }

        contact = contact_map.get(tx.id)
        if contact:
            cid = contact.id
            if cid not in contacts_dict:
                contacts_dict[cid] = {
                    "contact_id": cid,
                    "contact_name": contact.name,
                    "total_outstanding": 0,
                    "transactions": [],
                }
            contacts_dict[cid]["transactions"].append(tx_data)
            contacts_dict[cid]["total_outstanding"] += float(tx.uncleared_amount)
        else:
            unassigned_txs.append(tx_data)

    # Build summary by bracket
    summary = {label: 0.0 for _, _, label in _AGE_BRACKETS}
    for tx in all_transactions:
        age_days = (as_of - tx.transaction_date).days
        bracket = _age_bracket(age_days)
        summary[bracket] += float(tx.uncleared_amount)

    contacts_list = sorted(
        contacts_dict.values(), key=lambda c: c["total_outstanding"], reverse=True
    )

    result = {
        "contacts": contacts_list,
        "summary": summary,
    }
    if unassigned_txs:
        result["unassigned"] = {
            "total_outstanding": sum(t["outstanding"] for t in unassigned_txs),
            "transactions": unassigned_txs,
        }
    return result


@bp.route("/aging-receivables-detail", methods=["GET"])
def aging_receivables_detail():
    as_of, err = _parse_date("as_of")
    if err:
        return err
    try:
        result = _build_aging_detail(
            g.session, Account.AccountType.RECEIVABLE, as_of
        )
    except Exception as e:
        return jsonify(error=str(e)), 400
    return jsonify(result)


@bp.route("/aging-payables-detail", methods=["GET"])
def aging_payables_detail():
    as_of, err = _parse_date("as_of")
    if err:
        return err
    try:
        result = _build_aging_detail(
            g.session, Account.AccountType.PAYABLE, as_of
        )
    except Exception as e:
        return jsonify(error=str(e)), 400
    return jsonify(result)
