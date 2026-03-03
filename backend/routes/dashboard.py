"""Dashboard aggregation route."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify

from python_accounting.models import Account
from python_accounting.reports import IncomeStatement

from backend.models.product import Product
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

        # Inventory summary
        inv_products = session.query(Product).filter(
            Product.track_inventory.is_(True),
            Product.is_active.is_(True),
        ).all()
        inventory_value = sum(
            Decimal(str(p.quantity_on_hand or 0)) * Decimal(str(p.average_cost or 0))
            for p in inv_products
        )
        low_stock_count = sum(
            1 for p in inv_products
            if Decimal(str(p.quantity_on_hand or 0)) <= Decimal(str(p.reorder_point or 0))
        )

        result = {
            "total_cash": _dec(total_cash),
            "accounts_receivable": _dec(accounts_receivable),
            "accounts_payable": _dec(accounts_payable),
            "revenue_this_month": _dec(revenue_this_month),
            "expenses_this_month": _dec(expenses_this_month),
            "net_income_this_month": _dec(net_income_this_month),
            "inventory_value": _dec(inventory_value),
            "low_stock_count": low_stock_count,
        }
    except Exception as e:
        return jsonify(error=str(e)), 500

    return jsonify(result)
