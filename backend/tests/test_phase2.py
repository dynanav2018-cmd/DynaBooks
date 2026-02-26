"""Phase 2 API tests for DynaBooks Flask REST layer."""

import json
import pytest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine

from python_accounting.database.session import get_session
from python_accounting.models import (
    Base, Entity, Currency, Account, Tax, LineItem, Assignment,
)
from python_accounting.transactions import ClientInvoice, ClientReceipt, JournalEntry

from backend.models import CustomBase
from backend.models.contact import Contact
from backend.models.product import Product
from backend.models.transaction_contact import TransactionContact
from backend.services.seeder import CHART_OF_ACCOUNTS
from backend.app import create_app


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_engine():
    """In-memory SQLite engine with all tables."""
    eng = create_engine("sqlite://", echo=False).execution_options(
        include_deleted=False, ignore_isolation=False,
    )
    Base.metadata.create_all(eng)
    CustomBase.metadata.create_all(eng)
    return eng


@pytest.fixture(scope="module")
def seeded_engine(test_engine):
    """Seed the in-memory DB with entity, chart of accounts, GST."""
    s = get_session(test_engine)

    entity = Entity(name="DynaNav Systems Inc.", year_start=1, locale="en_CA")
    s.add(entity)
    s.flush()

    cad = Currency(name="Canadian Dollar", code="CAD", entity_id=entity.id)
    s.add(cad)
    s.flush()
    entity.currency_id = cad.id
    s.commit()

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

    gst_account = s.query(Account).filter(
        Account.account_type == Account.AccountType.CONTROL
    ).first()
    gst = Tax(
        name="GST", code="GST", rate=5,
        account_id=gst_account.id, entity_id=entity.id,
    )
    s.add(gst)
    s.commit()
    s.close()

    return test_engine


@pytest.fixture(scope="module")
def app(seeded_engine):
    """Flask test app with session factory returning fresh sessions."""
    def _session_factory():
        s = get_session(seeded_engine)
        entity = s.query(Entity).first()
        if entity:
            s.entity = entity
        return s

    application = create_app(session_factory=_session_factory)
    application.config["TESTING"] = True
    return application


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def session(seeded_engine):
    """Direct session for querying account IDs etc. in tests."""
    s = get_session(seeded_engine)
    entity = s.query(Entity).first()
    if entity:
        s.entity = entity
    yield s
    s.close()


# Shared state for dependent tests
_state = {}


# ── Helper ──────────────────────────────────────────────────────────

def post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


def put_json(client, url, data):
    return client.put(url, data=json.dumps(data), content_type="application/json")


# ── Test 1: GET /api/accounts returns 33 seeded accounts ───────────

def test_list_accounts(client):
    resp = client.get("/api/accounts")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == len(CHART_OF_ACCOUNTS)


# ── Test 2: POST /api/accounts creates new account ─────────────────

def test_create_account(client):
    resp = post_json(client, "/api/accounts", {
        "name": "Test Expense Account",
        "account_type": "Operating Expense",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Test Expense Account"
    assert data["id"] is not None


# ── Test 3: Contacts CRUD ──────────────────────────────────────────

def test_contacts_crud(client):
    # Create
    resp = post_json(client, "/api/contacts", {
        "name": "Acme Corp",
        "contact_type": "client",
        "email": "info@acme.com",
        "phone": "555-1234",
        "payment_terms_days": 45,
    })
    assert resp.status_code == 201
    contact = resp.get_json()
    assert contact["name"] == "Acme Corp"
    contact_id = contact["id"]

    # List
    resp = client.get("/api/contacts")
    assert resp.status_code == 200
    contacts = resp.get_json()
    assert any(c["id"] == contact_id for c in contacts)

    # Update
    resp = put_json(client, f"/api/contacts/{contact_id}", {
        "phone": "555-9999",
    })
    assert resp.status_code == 200
    assert resp.get_json()["phone"] == "555-9999"

    # Deactivate
    resp = client.delete(f"/api/contacts/{contact_id}")
    assert resp.status_code == 200

    # Should not appear in default list (inactive)
    resp = client.get("/api/contacts")
    contacts = resp.get_json()
    assert not any(c["id"] == contact_id for c in contacts)


# ── Test 4: Taxes CRUD ─────────────────────────────────────────────

def test_taxes_list(client):
    resp = client.get("/api/taxes")
    assert resp.status_code == 200
    taxes = resp.get_json()
    assert len(taxes) >= 1
    gst = next(t for t in taxes if t["code"] == "GST")
    assert gst["rate"] == 5.0


# ── Test 5: POST /api/invoices creates invoice with line items ─────

def test_create_invoice(client, session):
    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()
    gst = session.query(Tax).filter(Tax.code == "GST").first()

    resp = post_json(client, "/api/invoices", {
        "narration": "GPS System Sale",
        "transaction_date": "2026-03-15",
        "line_items": [
            {
                "narration": "DynaNav Pro",
                "account_id": revenue.id,
                "amount": 500,
                "quantity": 2,
                "tax_id": gst.id,
            }
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    invoice = resp.get_json()
    assert invoice["narration"] == "GPS System Sale"
    assert len(invoice["line_items"]) == 1
    # Amount = 500 * 2 + 5% GST = 1000 + 50 = 1050
    assert invoice["amount"] == 1050.0
    assert invoice["is_posted"] is False

    _state["invoice_id"] = invoice["id"]


# ── Test 6: POST /api/invoices/<id>/post ────────────────────────────

def test_post_invoice(client):
    invoice_id = _state["invoice_id"]
    resp = client.post(f"/api/invoices/{invoice_id}/post")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_posted"] is True


# ── Test 7: POST /api/receipts creates receipt ──────────────────────

def test_create_receipt(client, session):
    bank = session.query(Account).filter(
        Account.account_type == Account.AccountType.BANK
    ).first()

    resp = post_json(client, "/api/receipts", {
        "narration": "Payment from client",
        "transaction_date": "2026-03-20",
        "line_items": [
            {
                "narration": "Bank deposit",
                "account_id": bank.id,
                "amount": 1050,
            }
        ],
        "post": True,
    })
    assert resp.status_code == 201, resp.get_json()
    receipt = resp.get_json()
    assert receipt["amount"] == 1050.0
    assert receipt["is_posted"] is True

    _state["receipt_id"] = receipt["id"]


# ── Test 8: POST /api/assignments assigns receipt to invoice ────────

def test_create_assignment(client):
    invoice_id = _state["invoice_id"]
    receipt_id = _state["receipt_id"]

    resp = post_json(client, "/api/assignments", {
        "transaction_id": receipt_id,
        "assigned_id": invoice_id,
        "assigned_type": "ClientInvoice",
        "amount": 1050,
        "assignment_date": "2026-03-20",
    })
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data["amount"] == 1050.0


# ── Test 9: POST /api/journals with balanced entry succeeds ────────

def test_create_journal_balanced(client, session):
    bank = session.query(Account).filter(
        Account.account_type == Account.AccountType.BANK
    ).first()
    expense = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_EXPENSE,
        Account.description == "Spec #6300",
    ).first()

    resp = post_json(client, "/api/journals", {
        "narration": "Office supplies purchase via API",
        "transaction_date": "2026-03-18",
        "account_id": bank.id,
        "line_items": [
            {
                "narration": "Printer ink",
                "account_id": expense.id,
                "amount": 75,
            }
        ],
        "post": True,
    })
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data["is_posted"] is True


# ── Test 10: POST /api/journals with missing account_id returns 400 ─

def test_create_journal_missing_account(client):
    resp = post_json(client, "/api/journals", {
        "narration": "Bad entry",
        "transaction_date": "2026-03-18",
        "line_items": [
            {"narration": "x", "account_id": 1, "amount": 100}
        ],
    })
    assert resp.status_code == 400


# ── Test 11: GET /api/reports/income-statement returns structure ────

def test_income_statement_report(client):
    resp = client.get("/api/reports/income-statement?from=2026-01-02&to=2026-12-31")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "result_amounts" in data
    assert "NET_PROFIT" in data["result_amounts"]


# ── Test 12: GET /api/dashboard returns summary data ────────────────

def test_dashboard(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "total_cash" in data
    assert "accounts_receivable" in data
    assert "accounts_payable" in data
