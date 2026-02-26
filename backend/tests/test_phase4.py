"""Phase 4 tests — Bills, Journal deletion, Payments, Bill PDF, Assignments."""

import json
import pytest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine

from python_accounting.database.session import get_session
from python_accounting.models import (
    Base, Entity, Currency, Account, Tax, LineItem,
)
from python_accounting.transactions import SupplierBill, JournalEntry, SupplierPayment

from backend.models import CustomBase
from backend.models.contact import Contact
from backend.models.transaction_contact import TransactionContact
from backend.services.seeder import CHART_OF_ACCOUNTS
from backend.app import create_app


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_engine():
    eng = create_engine("sqlite://", echo=False).execution_options(
        include_deleted=False, ignore_isolation=False,
    )
    Base.metadata.create_all(eng)
    CustomBase.metadata.create_all(eng)
    return eng


@pytest.fixture(scope="module")
def seeded_engine(test_engine):
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
    s = get_session(seeded_engine)
    entity = s.query(Entity).first()
    if entity:
        s.entity = entity
    yield s
    s.close()


_state = {}


def post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


# ── Test 1: Create bill with line items ─────────────────────────────

def test_create_bill(client, session):
    expense = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_EXPENSE,
        Account.description == "Spec #6300",
    ).first()
    gst = session.query(Tax).filter(Tax.code == "GST").first()

    resp = post_json(client, "/api/bills", {
        "narration": "Office Supplies Purchase",
        "transaction_date": "2026-03-15",
        "line_items": [
            {
                "narration": "Printer paper",
                "account_id": expense.id,
                "amount": 200,
                "quantity": 2,
                "tax_id": gst.id,
            },
            {
                "narration": "Ink cartridges",
                "account_id": expense.id,
                "amount": 150,
                "quantity": 1,
            },
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    bill = resp.get_json()
    assert bill["narration"] == "Office Supplies Purchase"
    assert len(bill["line_items"]) == 2
    # 200*2 + 5% GST on 400 = 420 + 150 = 570
    assert bill["amount"] == 570.0
    assert bill["is_posted"] is False

    _state["bill_id"] = bill["id"]


# ── Test 2: Post a bill ─────────────────────────────────────────────

def test_post_bill(client):
    bill_id = _state["bill_id"]
    resp = client.post(f"/api/bills/{bill_id}/post")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_posted"] is True


# ── Test 3: Bill PDF generation ──────────────────────────────────────

def test_bill_pdf(client, session):
    # Create a supplier contact
    resp = post_json(client, "/api/contacts", {
        "name": "Office Depot",
        "contact_type": "supplier",
        "email": "orders@officedepot.com",
    })
    assert resp.status_code == 201
    contact_id = resp.get_json()["id"]

    expense = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_EXPENSE,
        Account.description == "Spec #6300",
    ).first()

    # Create and post a bill with contact
    resp = post_json(client, "/api/bills", {
        "narration": "PDF Test Bill",
        "transaction_date": "2026-04-10",
        "contact_id": contact_id,
        "post": True,
        "line_items": [
            {
                "narration": "Toner",
                "account_id": expense.id,
                "amount": 80,
                "quantity": 1,
            },
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    bill = resp.get_json()

    # Download PDF
    resp = client.get(f"/api/bills/{bill['id']}/pdf")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert len(resp.data) > 100


# ── Test 4: Bill PDF returns 404 for non-existent bill ──────────────

def test_bill_pdf_not_found(client):
    resp = client.get("/api/bills/99999/pdf")
    assert resp.status_code == 404


# ── Test 5: Create payment ──────────────────────────────────────────

def test_create_payment(client, session):
    bank = session.query(Account).filter(
        Account.account_type == Account.AccountType.BANK
    ).first()

    resp = post_json(client, "/api/payments", {
        "narration": "Payment to supplier",
        "transaction_date": "2026-03-20",
        "line_items": [
            {
                "narration": "Bank withdrawal",
                "account_id": bank.id,
                "amount": 570,
            },
        ],
        "post": True,
    })
    assert resp.status_code == 201, resp.get_json()
    payment = resp.get_json()
    assert payment["amount"] == 570.0
    assert payment["is_posted"] is True

    _state["payment_id"] = payment["id"]


# ── Test 6: Assign payment to bill ──────────────────────────────────

def test_assign_payment_to_bill(client):
    bill_id = _state["bill_id"]
    payment_id = _state["payment_id"]

    resp = post_json(client, "/api/assignments", {
        "transaction_id": payment_id,
        "assigned_id": bill_id,
        "assigned_type": "SupplierBill",
        "amount": 570,
        "assignment_date": "2026-03-20",
    })
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data["amount"] == 570.0


# ── Test 7: Create and delete journal entry ──────────────────────────

def test_journal_delete(client, session):
    bank = session.query(Account).filter(
        Account.account_type == Account.AccountType.BANK
    ).first()
    expense = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_EXPENSE,
        Account.description == "Spec #6300",
    ).first()

    # Create a journal entry (unposted)
    resp = post_json(client, "/api/journals", {
        "narration": "Temporary entry to delete",
        "transaction_date": "2026-03-18",
        "account_id": bank.id,
        "line_items": [
            {
                "narration": "Test delete",
                "account_id": expense.id,
                "amount": 25,
            },
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    journal_id = resp.get_json()["id"]

    # Delete it
    resp = client.delete(f"/api/journals/{journal_id}")
    assert resp.status_code == 200

    # Verify it's gone from the list
    resp = client.get("/api/journals")
    journals = resp.get_json()
    assert not any(j["id"] == journal_id for j in journals)


# ── Test 8: Cannot delete posted journal ─────────────────────────────

def test_cannot_delete_posted_journal(client, session):
    bank = session.query(Account).filter(
        Account.account_type == Account.AccountType.BANK
    ).first()
    expense = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_EXPENSE,
        Account.description == "Spec #6300",
    ).first()

    # Create and post
    resp = post_json(client, "/api/journals", {
        "narration": "Posted entry",
        "transaction_date": "2026-04-05",
        "account_id": bank.id,
        "line_items": [
            {
                "narration": "Cannot delete this",
                "account_id": expense.id,
                "amount": 50,
            },
        ],
        "post": True,
    })
    assert resp.status_code == 201, resp.get_json()
    journal_id = resp.get_json()["id"]

    # Try to delete — should fail
    resp = client.delete(f"/api/journals/{journal_id}")
    assert resp.status_code == 400
