"""Fiscal year-end closing service."""

from datetime import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from python_accounting.models import Account, Entity, LineItem
from python_accounting.models.reporting_period import ReportingPeriod
from python_accounting.reports import IncomeStatement
from python_accounting.transactions import JournalEntry


# Account types that get closed to Retained Earnings
_REVENUE_TYPES = {
    Account.AccountType.OPERATING_REVENUE,
    Account.AccountType.NON_OPERATING_REVENUE,
}

_EXPENSE_TYPES = {
    Account.AccountType.DIRECT_EXPENSE,
    Account.AccountType.OPERATING_EXPENSE,
    Account.AccountType.OVERHEAD_EXPENSE,
    Account.AccountType.OTHER_EXPENSE,
}

_CLOSABLE_TYPES = _REVENUE_TYPES | _EXPENSE_TYPES


def _current_period(session):
    """Return the current open or adjusting reporting period."""
    entity = session.entity
    period = (
        session.query(ReportingPeriod)
        .filter(
            ReportingPeriod.entity_id == entity.id,
            ReportingPeriod.status.in_([
                ReportingPeriod.Status.OPEN,
                ReportingPeriod.Status.ADJUSTING,
            ]),
        )
        .order_by(ReportingPeriod.calendar_year.desc())
        .first()
    )
    return period


def _period_dates(period, entity):
    """Return (start, end) datetime for a reporting period."""
    year = period.calendar_year
    start = datetime(year, entity.year_start, 1)
    end = start + relativedelta(years=1) - relativedelta(seconds=1)
    return start, end


def _retained_earnings_account(session):
    """Find the Retained Earnings equity account."""
    return (
        session.query(Account)
        .filter(
            Account.entity_id == session.entity.id,
            Account.account_type == Account.AccountType.EQUITY,
        )
        .filter(Account.name.ilike("%retained%"))
        .first()
    )


def preview_closing(session):
    """Preview what the year-end close would do.

    Returns a dict with period info, net income, and accounts to close.
    """
    period = _current_period(session)
    if not period:
        return {"error": "No open reporting period found"}

    entity = session.entity
    start, end = _period_dates(period, entity)

    # Use IncomeStatement to get the net income
    # Offset start by 1 second to avoid InvalidTransactionDateError
    report_start = start + relativedelta(seconds=1)
    income_stmt = IncomeStatement(session, report_start, end)

    # Collect accounts with non-zero balances
    accounts_to_close = []
    all_accounts = (
        session.query(Account)
        .filter(
            Account.entity_id == entity.id,
            Account.account_type.in_(_CLOSABLE_TYPES),
        )
        .all()
    )

    for acct in all_accounts:
        balance = acct.closing_balance(session)
        if balance and balance != Decimal(0):
            acct_type_str = acct.account_type.name
            is_revenue = acct.account_type in _REVENUE_TYPES
            accounts_to_close.append({
                "id": acct.id,
                "name": acct.name,
                "account_type": acct_type_str,
                "balance": float(balance),
                "action": "debit" if is_revenue else "credit",
            })

    net_income = Decimal(0)
    if income_stmt.result_amounts:
        for key, val in income_stmt.result_amounts.items():
            net_income = val
            break

    re_account = _retained_earnings_account(session)

    return {
        "period": {
            "calendar_year": period.calendar_year,
            "status": period.status.name,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "net_income": float(net_income),
        "retained_earnings_account": re_account.name if re_account else None,
        "accounts_to_close": accounts_to_close,
    }


def perform_closing(session):
    """Perform year-end close: create closing entries, mark period CLOSED.

    Creates one JournalEntry per revenue/expense account with a non-zero balance.
    Revenue accounts: debit revenue, credit Retained Earnings.
    Expense accounts: credit expense, debit Retained Earnings.
    """
    period = _current_period(session)
    if not period:
        raise ValueError("No open reporting period found")

    if period.status == ReportingPeriod.Status.CLOSED:
        raise ValueError("Period is already closed")

    entity = session.entity
    _, end = _period_dates(period, entity)
    closing_date = end.replace(hour=0, minute=0, second=0, microsecond=0)

    re_account = _retained_earnings_account(session)
    if not re_account:
        raise ValueError("Retained Earnings account not found")

    all_accounts = (
        session.query(Account)
        .filter(
            Account.entity_id == entity.id,
            Account.account_type.in_(_CLOSABLE_TYPES),
        )
        .all()
    )

    entries_created = 0
    for acct in all_accounts:
        balance = acct.closing_balance(session)
        if not balance or balance == Decimal(0):
            continue

        is_revenue = acct.account_type in _REVENUE_TYPES
        abs_balance = abs(balance)

        # Create a JournalEntry with Retained Earnings as the main account
        # Revenue: debit revenue account (line item), credit RE (main)
        # Expense: debit RE (main), credit expense account (line item)
        if is_revenue:
            journal = JournalEntry(
                narration=f"Year-end close: {acct.name}",
                transaction_date=closing_date,
                account_id=re_account.id,
                entity_id=entity.id,
            )
            session.add(journal)
            session.flush()

            line = LineItem(
                narration=f"Close {acct.name} to Retained Earnings",
                account_id=acct.id,
                amount=abs_balance,
                entity_id=entity.id,
            )
            session.add(line)
            session.flush()
            journal.line_items.add(line)
            session.flush()
        else:
            journal = JournalEntry(
                narration=f"Year-end close: {acct.name}",
                transaction_date=closing_date,
                account_id=acct.id,
                entity_id=entity.id,
                credited=False,
            )
            session.add(journal)
            session.flush()

            line = LineItem(
                narration=f"Close {acct.name} to Retained Earnings",
                account_id=re_account.id,
                amount=abs_balance,
                entity_id=entity.id,
                credited=False,
            )
            session.add(line)
            session.flush()
            journal.line_items.add(line)
            session.flush()

        journal.post(session)
        entries_created += 1

    # Mark the period as CLOSED
    period.status = ReportingPeriod.Status.CLOSED
    session.add(period)
    session.commit()

    return {
        "message": f"Year-end close complete. {entries_created} closing entries created.",
        "entries_created": entries_created,
        "period_status": "CLOSED",
    }
