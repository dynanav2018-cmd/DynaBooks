"""Dashboard aggregation route."""

from datetime import datetime

from flask import Blueprint, g, jsonify

from python_accounting.models import Account
from python_accounting.reports import IncomeStatement

from backend.serializers import _dec

bp = Blueprint("dashboard", __name__, url_prefix="/api")


@bp.route("/dashboard", methods=["GET"])
def dashboard():
    session = g.session
    now = datetime.now()
    month_start = datetime(now.year, now.month, 2)  # avoid period start date
    month_end = datetime(now.year, now.month, 28)  # safe end-of-month

    try:
        # Cash balance (sum of all BANK accounts)
        banks = session.query(Account).filter(
            Account.account_type == Account.AccountType.BANK
        ).all()
        total_cash = sum(a.closing_balance(session, now) for a in banks)

        # Accounts Receivable
        receivables = session.query(Account).filter(
            Account.account_type == Account.AccountType.RECEIVABLE
        ).all()
        accounts_receivable = sum(a.closing_balance(session, now) for a in receivables)

        # Accounts Payable
        payables = session.query(Account).filter(
            Account.account_type == Account.AccountType.PAYABLE
        ).all()
        accounts_payable = sum(a.closing_balance(session, now) for a in payables)

        # Income statement for this month
        revenue_this_month = 0
        expenses_this_month = 0
        net_income_this_month = 0
        try:
            stmt = IncomeStatement(session, month_start, month_end)
            revenue_this_month = stmt.result_amounts.get("TOTAL_REVENUE", 0)
            total_expenses = stmt.result_amounts.get("TOTAL_EXPENSES", 0)
            expenses_this_month = total_expenses
            net_income_this_month = stmt.result_amounts.get("NET_PROFIT", 0)
        except Exception:
            pass

        result = {
            "total_cash": _dec(total_cash),
            "accounts_receivable": _dec(accounts_receivable),
            "accounts_payable": _dec(accounts_payable),
            "revenue_this_month": _dec(revenue_this_month),
            "expenses_this_month": _dec(expenses_this_month),
            "net_income_this_month": _dec(net_income_this_month),
        }
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify(result)
