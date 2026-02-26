"""Phase 3 tests for PDF generation endpoints."""

import json
import pytest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine

from python_accounting.database.session import get_session
from python_accounting.models import (
    Base, Entity, Currency, Account, Tax, LineItem,
)
from python_accounting.transactions import ClientInvoice

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


# ── Test 1: Create and post an invoice, then download its PDF ──────

def test_invoice_pdf(client, session):
    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()
    gst = session.query(Tax).filter(Tax.code == "GST").first()

    # Create a contact first
    resp = post_json(client, "/api/contacts", {
        "name": "PDF Test Client",
        "contact_type": "client",
        "email": "pdf@test.com",
    })
    assert resp.status_code == 201
    contact_id = resp.get_json()["id"]

    # Create invoice with contact
    resp = post_json(client, "/api/invoices", {
        "narration": "PDF Test Invoice",
        "transaction_date": "2026-06-15",
        "contact_id": contact_id,
        "post": True,
        "line_items": [
            {
                "narration": "Widget A",
                "account_id": revenue.id,
                "amount": 250,
                "quantity": 3,
                "tax_id": gst.id,
            },
            {
                "narration": "Widget B",
                "account_id": revenue.id,
                "amount": 100,
                "quantity": 1,
            },
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    invoice = resp.get_json()
    _state["invoice_id"] = invoice["id"]

    # Download PDF
    resp = client.get(f"/api/invoices/{invoice['id']}/pdf")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert len(resp.data) > 100  # non-trivial PDF content


# ── Test 2: Invoice PDF returns 404 for non-existent invoice ────────

def test_invoice_pdf_not_found(client):
    resp = client.get("/api/invoices/99999/pdf")
    assert resp.status_code == 404


# ── Test 3: Income statement report PDF ─────────────────────────────

def test_income_statement_pdf(client):
    resp = client.get(
        "/api/reports/income-statement/pdf?from=2026-01-02&to=2026-12-31"
    )
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert len(resp.data) > 100


# ── Test 4: Balance sheet report PDF ────────────────────────────────

def test_balance_sheet_pdf(client):
    resp = client.get("/api/reports/balance-sheet/pdf?as_of=2026-12-31")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"


# ── Test 5: Unknown report type returns 400 ─────────────────────────

def test_unknown_report_pdf(client):
    resp = client.get("/api/reports/nonexistent/pdf")
    assert resp.status_code == 400


# ── Test 6: PDF service renders valid PDF bytes ─────────────────────

def test_pdf_service_directly():
    from backend.services.pdf_service import render_invoice_pdf

    invoice_data = {
        "transaction_no": "INV-TEST-001",
        "transaction_date": "2026-06-15",
        "is_posted": True,
        "amount": 525.0,
        "line_items": [
            {"narration": "Test Item", "quantity": 1, "amount": 525.0}
        ],
        "tax": None,
    }
    company_data = {"name": "Test Company", "locale": "en_CA"}
    pdf = render_invoice_pdf(invoice_data, company_data)
    assert pdf[:5] == b"%PDF-"
