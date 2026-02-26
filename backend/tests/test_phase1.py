"""Phase 1 verification tests for DynaBooks accounting engine."""

import pytest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine

from python_accounting.database.session import get_session
from python_accounting.models import (
    Base, Entity, Currency, Account, Tax, LineItem,
    Assignment, ReportingPeriod, Ledger, Balance,
)
from python_accounting.transactions import ClientInvoice, ClientReceipt, JournalEntry
from python_accounting.reports import IncomeStatement

from backend.services.seeder import CHART_OF_ACCOUNTS


@pytest.fixture(scope="module")
def session():
    """In-memory database with full seed data, isolated from production DB."""
    test_engine = create_engine("sqlite://", echo=False).execution_options(
        include_deleted=False, ignore_isolation=False,
    )
    Base.metadata.create_all(test_engine)
    s = get_session(test_engine)

    # Entity (sets session.entity via event listener, creates ReportingPeriod)
    entity = Entity(name="DynaNav Systems Inc.", year_start=1, locale="en_CA")
    s.add(entity)
    s.flush()

    # Currency
    cad = Currency(name="Canadian Dollar", code="CAD", entity_id=entity.id)
    s.add(cad)
    s.flush()
    entity.currency_id = cad.id
    s.commit()

    # Chart of Accounts (one at a time for proper auto-code generation)
    for name, account_type, spec_code in CHART_OF_ACCOUNTS:
        acct = Account(
            name=name,
            account_type=account_type,
            currency_id=cad.id,
            entity_id=entity.id,
            description=f"Spec #{spec_code}",
        )
        s.add(acct)
        s.flush()
    s.commit()

    # GST Tax
    gst_account = s.query(Account).filter(
        Account.account_type == Account.AccountType.CONTROL
    ).first()
    gst = Tax(
        name="GST", code="GST", rate=5,
        account_id=gst_account.id, entity_id=entity.id,
    )
    s.add(gst)
    s.commit()

    yield s
    s.close()


# ── Test 1: Entity, Currency, ReportingPeriod ─────────────────────────

def test_entity_currency_reporting_period(session):
    entity = session.entity
    assert entity.name == "DynaNav Systems Inc."
    assert entity.year_start == 1

    currency = session.query(Currency).first()
    assert currency.code == "CAD"
    assert currency.name == "Canadian Dollar"
    assert entity.currency_id == currency.id

    rp = session.query(ReportingPeriod).first()
    assert rp.calendar_year == datetime.today().year
    assert rp.period_count == 1
    assert rp.status == ReportingPeriod.Status.OPEN


# ── Test 2: Chart of Accounts ─────────────────────────────────────────

def test_chart_of_accounts(session):
    accounts = session.query(Account).all()
    assert len(accounts) == len(CHART_OF_ACCOUNTS)  # 33 accounts

    # Verify type counts match seed data
    expected_counts = {}
    for _, acct_type, _ in CHART_OF_ACCOUNTS:
        expected_counts[acct_type] = expected_counts.get(acct_type, 0) + 1

    actual_counts = {}
    for acct in accounts:
        actual_counts[acct.account_type] = actual_counts.get(acct.account_type, 0) + 1

    assert actual_counts == expected_counts

    # Verify specific key accounts exist
    receivable = session.query(Account).filter(
        Account.account_type == Account.AccountType.RECEIVABLE
    ).all()
    assert len(receivable) == 1

    banks = session.query(Account).filter(
        Account.account_type == Account.AccountType.BANK
    ).all()
    assert len(banks) == 3


# ── Test 3: GST Tax ───────────────────────────────────────────────────

def test_gst_tax(session):
    tax = session.query(Tax).filter(Tax.code == "GST").first()
    assert tax is not None
    assert tax.name == "GST"
    assert tax.rate == Decimal("5")

    # Linked to a CONTROL account
    control_account = session.get(Account, tax.account_id)
    assert control_account.account_type == Account.AccountType.CONTROL


# ── Test 4: Journal Entry — debits equal credits ──────────────────────

def test_journal_entry_debits_equal_credits(session):
    entity = session.entity

    bank = session.query(Account).filter(
        Account.account_type == Account.AccountType.BANK
    ).first()

    office_supplies = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_EXPENSE,
        Account.description == "Spec #6300",
    ).first()

    # Create journal entry: debit Office Supplies, credit Bank
    journal = JournalEntry(
        narration="Office supplies purchase",
        transaction_date=datetime(2026, 2, 15),
        account_id=bank.id,
        entity_id=entity.id,
    )
    session.add(journal)
    session.flush()

    line = LineItem(
        narration="Printer paper and toner",
        account_id=office_supplies.id,
        amount=Decimal("150.00"),
        entity_id=entity.id,
    )
    session.add(line)
    session.flush()

    journal.line_items.add(line)
    session.flush()

    journal.post(session)
    session.commit()

    # Verify ledger entries balance: total debits == total credits
    ledgers = session.query(Ledger).filter(
        Ledger.transaction_id == journal.id
    ).all()
    assert len(ledgers) > 0

    debits = sum(l.amount for l in ledgers if l.entry_type == Balance.BalanceType.DEBIT)
    credits = sum(l.amount for l in ledgers if l.entry_type == Balance.BalanceType.CREDIT)
    assert debits == credits
    assert debits == Decimal("150.0000")


# ── Test 5: Client Invoice with tax ───────────────────────────────────

def test_client_invoice_with_tax(session):
    entity = session.entity

    receivable = session.query(Account).filter(
        Account.account_type == Account.AccountType.RECEIVABLE
    ).first()

    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()

    gst = session.query(Tax).filter(Tax.code == "GST").first()

    invoice = ClientInvoice(
        narration="GPS system sale to client",
        transaction_date=datetime(2026, 2, 16),
        account_id=receivable.id,
        entity_id=entity.id,
    )
    session.add(invoice)
    session.flush()

    line = LineItem(
        narration="DynaNav Pro GPS Unit",
        account_id=revenue.id,
        amount=Decimal("1000.00"),
        quantity=Decimal("1"),
        tax_id=gst.id,
        entity_id=entity.id,
    )
    session.add(line)
    session.flush()

    invoice.line_items.add(line)
    session.flush()

    invoice.post(session)
    session.commit()

    # Invoice amount = line total + GST = 1000 + 50 = 1050
    assert invoice.amount == Decimal("1050")

    # Verify tax breakdown
    assert invoice.tax["total"] == Decimal("50")

    # Store invoice id for receipt test
    session.info["test_invoice_id"] = invoice.id


# ── Test 6: Client Receipt + Assignment ───────────────────────────────

def test_client_receipt_and_assignment(session):
    entity = session.entity
    invoice_id = session.info["test_invoice_id"]
    invoice = session.get(ClientInvoice, invoice_id)

    receivable = session.query(Account).filter(
        Account.account_type == Account.AccountType.RECEIVABLE
    ).first()

    bank = session.query(Account).filter(
        Account.account_type == Account.AccountType.BANK
    ).first()

    # Create receipt for full invoice amount
    receipt = ClientReceipt(
        narration="Payment received for GPS system",
        transaction_date=datetime(2026, 2, 20),
        account_id=receivable.id,
        entity_id=entity.id,
    )
    session.add(receipt)
    session.flush()

    line = LineItem(
        narration="Bank deposit",
        account_id=bank.id,
        amount=Decimal("1050.00"),
        entity_id=entity.id,
    )
    session.add(line)
    session.flush()

    receipt.line_items.add(line)
    session.flush()

    receipt.post(session)
    session.commit()

    assert receipt.amount == Decimal("1050")

    # Assign receipt to invoice (clears the receivable)
    assignment = Assignment(
        assignment_date=datetime(2026, 2, 20),
        transaction_id=receipt.id,
        assigned_id=invoice.id,
        assigned_type="ClientInvoice",
        amount=Decimal("1050"),
        entity_id=entity.id,
    )
    session.add(assignment)
    session.commit()

    # Invoice should now be fully cleared
    assert invoice.cleared(session) == Decimal("1050")
    assert receipt.balance(session) == Decimal("0")


# ── Test 7: Income Statement ──────────────────────────────────────────

def test_income_statement(session):
    start = datetime(2026, 1, 2)
    end = datetime(2026, 12, 31)

    statement = IncomeStatement(session, start, end)

    # Revenue: $1000 from invoice (operating revenue)
    # Expense: $150 from journal entry (operating expense)
    # Net profit: 1000 - 150 = 850
    net_profit = statement.result_amounts["NET_PROFIT"]
    assert net_profit == Decimal("850"), f"Expected 850, got {net_profit}"

    gross_profit = statement.result_amounts["GROSS_PROFIT"]
    assert gross_profit == Decimal("850"), f"Expected 850, got {gross_profit}"
