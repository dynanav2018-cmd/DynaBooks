"""Financial Reports routes."""

from datetime import datetime

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Account
from python_accounting.reports import (
    IncomeStatement,
    BalanceSheet,
    TrialBalance,
    CashflowStatement,
    AgingSchedule,
)

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
