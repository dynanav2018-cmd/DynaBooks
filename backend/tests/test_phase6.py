"""Phase 6 tests: products & recurring, full invoice/bill editing,
company address, contact address fields.
"""

import json
import os

import pytest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine

from python_accounting.database.session import get_session
from python_accounting.models import (
    Base, Entity, Currency, Account, Tax, LineItem,
)
from python_accounting.transactions import ClientInvoice, SupplierBill

from backend.models import CustomBase
from backend.models.contact import Contact
from backend.models.product import Product
from backend.models.company_info import CompanyInfo
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

    entity = Entity(name="Phase6 Test Corp", year_start=1, locale="en_CA")
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


def post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


def put_json(client, url, data):
    return client.put(url, data=json.dumps(data), content_type="application/json")


# ── Test 1: Product default type ─────────────────────────────────

def test_create_product_default_type(client, session):
    """Product without type defaults to 'product'."""
    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()

    resp = post_json(client, "/api/products", {
        "name": "GPS Module",
        "default_price": 250.00,
        "revenue_account_id": revenue.id,
    })
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data["product_type"] == "product"
    assert data["revenue_account_id"] == revenue.id
    assert data["expense_account_id"] is None


# ── Test 2: Create recurring expense ─────────────────────────────

def test_create_recurring_expense(client, session):
    """Recurring with expense_account_id succeeds."""
    expense = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_EXPENSE
    ).first()

    resp = post_json(client, "/api/products", {
        "name": "Hydro",
        "default_price": 150.00,
        "product_type": "recurring",
        "expense_account_id": expense.id,
    })
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert data["product_type"] == "recurring"
    assert data["expense_account_id"] == expense.id
    assert data["revenue_account_id"] is None


# ── Test 3: List products by type ────────────────────────────────

def test_list_products_by_type(client, session):
    """?type=recurring filters correctly."""
    resp = client.get("/api/products?type=recurring")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) >= 1
    for p in data:
        assert p["product_type"] == "recurring"

    resp = client.get("/api/products?type=product")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) >= 1
    for p in data:
        assert p["product_type"] == "product"


# ── Test 4: Edit draft invoice line items ────────────────────────

def test_edit_draft_invoice_line_items(client, session):
    """PUT with new line_items replaces existing."""
    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()

    # Create draft invoice with 1 line item
    resp = post_json(client, "/api/invoices", {
        "narration": "Draft for edit test",
        "transaction_date": "2026-06-15",
        "line_items": [
            {"narration": "Original item", "account_id": revenue.id, "amount": 100, "quantity": 1}
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    invoice_id = resp.get_json()["id"]
    assert len(resp.get_json()["line_items"]) == 1

    # Edit: replace with 2 line items
    resp = put_json(client, f"/api/invoices/{invoice_id}", {
        "narration": "Updated invoice",
        "transaction_date": "2026-06-16",
        "line_items": [
            {"narration": "New item A", "account_id": revenue.id, "amount": 200, "quantity": 1},
            {"narration": "New item B", "account_id": revenue.id, "amount": 300, "quantity": 2},
        ],
    })
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["narration"] == "Updated invoice"
    assert len(data["line_items"]) == 2
    narrations = sorted([li["narration"] for li in data["line_items"]])
    assert narrations == ["New item A", "New item B"]


# ── Test 5: Edit posted invoice rejected ─────────────────────────

def test_edit_posted_invoice_rejected(client, session):
    """PUT on posted invoice returns 400."""
    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()

    resp = post_json(client, "/api/invoices", {
        "narration": "Posted invoice",
        "transaction_date": "2026-06-17",
        "post": True,
        "line_items": [
            {"narration": "Item", "account_id": revenue.id, "amount": 500, "quantity": 1}
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    invoice_id = resp.get_json()["id"]

    resp = put_json(client, f"/api/invoices/{invoice_id}", {
        "narration": "Should fail",
    })
    assert resp.status_code == 400
    assert "posted" in resp.get_json()["error"].lower()


# ── Test 6: Edit draft bill ──────────────────────────────────────

def test_edit_draft_bill(client, session):
    """PUT with full payload updates bill correctly."""
    expense = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_EXPENSE
    ).first()

    # Create draft bill
    resp = post_json(client, "/api/bills", {
        "narration": "Draft bill",
        "transaction_date": "2026-06-15",
        "line_items": [
            {"narration": "Original expense", "account_id": expense.id, "amount": 80, "quantity": 1}
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    bill_id = resp.get_json()["id"]

    # Edit: new line items
    resp = put_json(client, f"/api/bills/{bill_id}", {
        "narration": "Updated bill",
        "line_items": [
            {"narration": "Office supplies", "account_id": expense.id, "amount": 120, "quantity": 1},
        ],
    })
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["narration"] == "Updated bill"
    assert len(data["line_items"]) == 1
    assert data["line_items"][0]["narration"] == "Office supplies"


# ── Test 7: Company info CRUD ────────────────────────────────────

def test_company_info_crud(client, session):
    """PUT /api/company with address creates CompanyInfo."""
    resp = put_json(client, "/api/company", {
        "name": "Phase6 Test Corp",
        "address_line_1": "123 Main St",
        "city": "Ottawa",
        "province_state": "ON",
        "postal_code": "K1A 0A6",
        "country": "Canada",
        "phone": "613-555-0123",
        "email": "info@phase6test.com",
    })
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["company_info"] is not None
    info = data["company_info"]
    assert info["address_line_1"] == "123 Main St"
    assert info["city"] == "Ottawa"
    assert info["province_state"] == "ON"
    assert info["postal_code"] == "K1A 0A6"
    assert info["country"] == "Canada"
    assert info["phone"] == "613-555-0123"
    assert info["email"] == "info@phase6test.com"

    # GET should also include company_info
    resp = client.get("/api/company")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["company_info"]["city"] == "Ottawa"


# ── Test 8: Contact address fields ───────────────────────────────

def test_contact_address_fields(client):
    """Contact with addresses persists via contact_addresses table."""
    resp = post_json(client, "/api/contacts", {
        "name": "Address Test Client",
        "contact_type": "client",
        "addresses": [{
            "address_type": "Mailing Address",
            "address_line_1": "456 Oak Ave",
            "city": "Toronto",
            "province_state": "ON",
            "postal_code": "M5V 2H1",
            "country": "CA",
        }],
    })
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    assert len(data["addresses"]) == 1
    addr = data["addresses"][0]
    assert addr["city"] == "Toronto"
    assert addr["province_state"] == "ON"
    assert addr["postal_code"] == "M5V 2H1"

    # Update address via sub-route
    contact_id = data["id"]
    addr_id = addr["id"]
    from flask import Flask
    resp = put_json(client, f"/api/contacts/{contact_id}/addresses/{addr_id}", {
        "city": "Mississauga",
    })
    assert resp.status_code == 200
    assert resp.get_json()["city"] == "Mississauga"


# ── Test 9: Invoice PDF with company address ─────────────────────

def test_invoice_pdf_with_company_address(client, session):
    """PDF renders company address."""
    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()

    # Create contact with full address
    resp = post_json(client, "/api/contacts", {
        "name": "PDF Address Test Corp",
        "contact_type": "client",
        "address_line_1": "789 Pine Rd",
        "city": "Vancouver",
        "province_state": "BC",
        "postal_code": "V6B 1A1",
    })
    assert resp.status_code == 201, resp.get_json()
    contact_id = resp.get_json()["id"]

    # Create and post invoice
    resp = post_json(client, "/api/invoices", {
        "narration": "PDF address test",
        "transaction_date": "2026-06-20",
        "contact_id": contact_id,
        "post": True,
        "line_items": [
            {"narration": "Service", "account_id": revenue.id, "amount": 1000, "quantity": 1}
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    invoice_id = resp.get_json()["id"]

    # Generate PDF
    resp = client.get(f"/api/invoices/{invoice_id}/pdf")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert resp.data[:5] == b"%PDF-"
