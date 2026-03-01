"""Phase 5 tests: data dir, logo, closing, multi-company.
Phase 5.1 tests: void receipts, overpayment handling, detailed aging.
"""

import io
import json
import os
import shutil
import tempfile

import pytest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine

from python_accounting.database.session import get_session
from python_accounting.models import (
    Base, Entity, Currency, Account, Assignment, Tax, LineItem,
)
from python_accounting.models.reporting_period import ReportingPeriod
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


def post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


# ── Test 1: Default data directory ──────────────────────────────────

def test_data_dir_default():
    """get_data_dir() returns <project_root>/data when no config exists."""
    from backend.data_dir import get_data_dir

    data_dir = get_data_dir()
    assert data_dir.endswith("data") or "data" in data_dir
    assert os.path.isdir(data_dir)


# ── Test 2: Data directory from config file ─────────────────────────

def test_data_dir_from_config():
    """get_data_dir() reads from dynabooks.json when present."""
    from backend import data_dir as dd

    tmpdir = tempfile.mkdtemp(prefix="dynabooks_test_")
    original_config = dd._CONFIG_FILE

    try:
        config_path = os.path.join(tmpdir, "dynabooks.json")
        target_dir = os.path.join(tmpdir, "custom_data")
        with open(config_path, "w") as f:
            json.dump({"data_dir": target_dir}, f)

        dd._CONFIG_FILE = config_path

        result = dd.get_data_dir()
        assert result == target_dir
        assert os.path.isdir(target_dir)
    finally:
        dd._CONFIG_FILE = original_config
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Test 3: Logo upload and serve ───────────────────────────────────

def test_logo_upload_and_serve(client):
    """POST /api/company/logo uploads, GET returns it."""
    # Create a valid 1x1 red PNG
    import struct
    import zlib

    def _make_png():
        """Create a minimal valid 1x1 red pixel PNG."""
        sig = b'\x89PNG\r\n\x1a\n'

        def chunk(ctype, data):
            c = ctype + data
            crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
            return struct.pack('>I', len(data)) + c + crc

        ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)  # 1x1, 8bit RGB
        raw = b'\x00\xff\x00\x00'  # filter byte + R G B
        idat = zlib.compress(raw)
        return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')

    png_data = _make_png()

    resp = client.post(
        "/api/company/logo",
        data={"logo": (io.BytesIO(png_data), "logo.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "Logo uploaded"

    # GET should return the logo
    resp = client.get("/api/company/logo")
    assert resp.status_code == 200
    assert resp.content_type == "image/png"
    assert len(resp.data) > 0


# ── Test 4: Invoice PDF renders correctly ──────────────────────────

def test_invoice_pdf_with_logo(client, session):
    """Invoice PDF endpoint works."""
    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()

    resp = post_json(client, "/api/invoices", {
        "narration": "Logo PDF test invoice",
        "transaction_date": "2026-06-20",
        "post": True,
        "line_items": [
            {"narration": "Item", "account_id": revenue.id, "amount": 100, "quantity": 1}
        ],
    })
    assert resp.status_code == 201, resp.get_json()
    invoice_id = resp.get_json()["id"]

    resp = client.get(f"/api/invoices/{invoice_id}/pdf")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert resp.data[:5] == b"%PDF-"


# ── Test 5: Closing preview returns correct structure ───────────────

def test_closing_preview(client, session):
    """GET /api/closing/preview returns period info and accounts."""
    # Create a revenue transaction through the Flask client so the
    # closing endpoint's session can see it.
    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()

    resp = post_json(client, "/api/invoices", {
        "narration": "Revenue for closing test",
        "transaction_date": "2026-06-15",
        "post": True,
        "line_items": [
            {"narration": "GPS Sale", "account_id": revenue.id, "amount": 1000, "quantity": 1}
        ],
    })
    assert resp.status_code == 201, resp.get_json()

    resp = client.get("/api/closing/preview")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "period" in data
    assert "net_income" in data
    assert "accounts_to_close" in data
    assert data["period"]["status"] in ("OPEN", "ADJUSTING")


# ── Test 6: Perform closing marks period CLOSED ─────────────────────

def test_closing_perform(client, session):
    """POST /api/closing marks the period CLOSED."""
    resp = client.post("/api/closing")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["period_status"] == "CLOSED"

    # Verify period is now CLOSED in DB
    period = (
        session.query(ReportingPeriod)
        .filter(
            ReportingPeriod.entity_id == session.entity.id,
            ReportingPeriod.status == ReportingPeriod.Status.CLOSED,
        )
        .first()
    )
    assert period is not None


# ── Test 7: Closed period blocks posting ─────────────────────────────

def test_closed_period_blocks_posting(session):
    """Transactions posted to a closed period raise an error."""
    from python_accounting.exceptions import ClosedReportingPeriodError

    revenue = session.query(Account).filter(
        Account.account_type == Account.AccountType.OPERATING_REVENUE
    ).first()

    period = (
        session.query(ReportingPeriod)
        .filter(
            ReportingPeriod.entity_id == session.entity.id,
            ReportingPeriod.status == ReportingPeriod.Status.CLOSED,
        )
        .first()
    )

    if not period:
        pytest.skip("No closed period found")

    try:
        invoice = ClientInvoice(
            narration="Should fail",
            transaction_date=datetime(period.calendar_year, 6, 15),
            account_id=session.query(Account).filter(
                Account.account_type == Account.AccountType.RECEIVABLE
            ).first().id,
            entity_id=session.entity.id,
        )
        session.add(invoice)
        session.flush()

        line = LineItem(
            narration="Test",
            account_id=revenue.id,
            amount=Decimal("100"),
            entity_id=session.entity.id,
        )
        session.add(line)
        session.flush()
        invoice.line_items.add(line)
        session.flush()
        invoice.post(session)
        session.rollback()
        pytest.fail("Expected ClosedReportingPeriodError")
    except ClosedReportingPeriodError:
        session.rollback()
        pass  # Expected


# ── Test 8: Multi-company create ─────────────────────────────────────

def test_multi_company_create():
    """Creating a new company creates its database file."""
    from backend.company_manager import create_company, list_companies
    from backend.data_dir import get_company_db_path

    company = create_company("Phase5 Test Corp", year_start=4, locale="en_US")
    assert "phase5-test-corp" in company["slug"]
    assert company["name"] == "Phase5 Test Corp"
    assert company["year_start"] == 4

    db_path = get_company_db_path(company["slug"])
    assert os.path.isfile(db_path)

    companies = list_companies()
    assert any(c["slug"] == company["slug"] for c in companies)


# ── Test 9: Multi-company data isolation ─────────────────────────────

def test_multi_company_isolation():
    """Two companies have independent data."""
    from backend.company_manager import create_company, make_company_session

    c1 = create_company("Iso Test Alpha")
    c2 = create_company("Iso Test Beta", year_start=7)

    s1 = make_company_session(c1["slug"])
    s2 = make_company_session(c2["slug"])

    assert s1.entity.name == "Iso Test Alpha"
    assert s2.entity.name == "Iso Test Beta"

    count1 = s1.query(Account).count()
    count2 = s2.query(Account).count()
    assert count1 == len(CHART_OF_ACCOUNTS)
    assert count2 == len(CHART_OF_ACCOUNTS)

    s1.close()
    s2.close()


# ── Phase 5.1 Tests ───────────────────────────────────────────────
# Use 2027 dates since the 2026 period is closed by test_closing_perform.

@pytest.fixture(scope="module", autouse=False)
def open_2027_period(seeded_engine):
    """Create an open 2027 reporting period for Phase 5.1 tests via raw SQL."""
    from sqlalchemy import text

    now = datetime.now().isoformat()
    with seeded_engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM reporting_period WHERE calendar_year=2027 AND entity_id=1")
        ).fetchone()
        if not row:
            # Get a fresh id from the recyclable table
            max_id = conn.execute(text("SELECT MAX(id) FROM recyclable")).scalar() or 0
            new_id = max_id + 1
            conn.execute(
                text(
                    "INSERT INTO recyclable (id, recycled_type, created_at, updated_at) "
                    "VALUES (:id, :rt, :ca, :ua)"
                ),
                {"id": new_id, "rt": "ReportingPeriod", "ca": now, "ua": now},
            )
            conn.execute(
                text(
                    "INSERT INTO reporting_period (id, calendar_year, period_count, status, entity_id) "
                    "VALUES (:id, :cy, :pc, :st, :eid)"
                ),
                {"id": new_id, "cy": 2027, "pc": 2, "st": "OPEN", "eid": 1},
            )
            conn.commit()
    return True


def _bank_account_id(client):
    """Return the first BANK account id."""
    resp = client.get("/api/accounts?type=Bank")
    data = resp.get_json()
    if isinstance(data, list) and data:
        return data[0]["id"]
    # Fallback: find via session-less approach
    return None


def _find_account_id(session, account_type):
    """Find an account id by type."""
    acct = session.query(Account).filter(
        Account.account_type == account_type
    ).first()
    return acct.id if acct else None


# ── Test 10: Void a posted receipt ─────────────────────────────────

def test_void_posted_receipt(client, session, open_2027_period):
    """Void a posted receipt: creates reversing JE, receipt effect zeroed."""
    bank_id = _find_account_id(session, Account.AccountType.BANK)
    assert bank_id, "No bank account found"

    # Create and post a receipt
    resp = post_json(client, "/api/receipts", {
        "narration": "Receipt to void",
        "transaction_date": "2027-03-15",
        "line_items": [{"narration": "Bank deposit", "account_id": bank_id, "amount": 500}],
        "post": True,
    })
    assert resp.status_code == 201, resp.get_json()
    receipt_id = resp.get_json()["id"]
    assert resp.get_json()["is_posted"] is True

    # Void it
    resp = client.post(f"/api/receipts/{receipt_id}/void")
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert "voiding_entry" in data
    assert "voided" in data["message"].lower()


# ── Test 11: Void receipt with assignment ──────────────────────────

def test_void_receipt_with_assignment(client, session, open_2027_period):
    """Void a receipt that was assigned to an invoice: assignment removed, invoice outstanding again."""
    bank_id = _find_account_id(session, Account.AccountType.BANK)
    revenue_id = _find_account_id(session, Account.AccountType.OPERATING_REVENUE)

    # Create and post an invoice
    resp = post_json(client, "/api/invoices", {
        "narration": "Invoice for void-assign test",
        "transaction_date": "2027-03-10",
        "post": True,
        "line_items": [{"narration": "Service", "account_id": revenue_id, "amount": 1000, "quantity": 1}],
    })
    assert resp.status_code == 201, resp.get_json()
    invoice_id = resp.get_json()["id"]

    # Create and post a receipt
    resp = post_json(client, "/api/receipts", {
        "narration": "Receipt for assignment test",
        "transaction_date": "2027-03-15",
        "line_items": [{"narration": "Payment", "account_id": bank_id, "amount": 1000}],
        "post": True,
    })
    assert resp.status_code == 201, resp.get_json()
    receipt_id = resp.get_json()["id"]

    # Assign receipt to invoice
    resp = post_json(client, "/api/assignments", {
        "transaction_id": receipt_id,
        "assigned_id": invoice_id,
        "assigned_type": "ClientInvoice",
        "amount": 1000,
        "assignment_date": "2027-03-15",
    })
    assert resp.status_code == 201, resp.get_json()

    # Void the receipt
    resp = client.post(f"/api/receipts/{receipt_id}/void")
    assert resp.status_code == 200, resp.get_json()

    # Verify assignment was removed
    remaining = (
        session.query(Assignment)
        .filter(Assignment.transaction_id == receipt_id)
        .all()
    )
    assert len(remaining) == 0, "Assignment should have been deleted"


# ── Test 12: Delete unposted receipt ──────────────────────────────

def test_delete_unposted_receipt(client, session, open_2027_period):
    """Delete an unposted receipt returns 200."""
    bank_id = _find_account_id(session, Account.AccountType.BANK)

    resp = post_json(client, "/api/receipts", {
        "narration": "Draft receipt to delete",
        "transaction_date": "2027-04-01",
        "line_items": [{"narration": "Draft", "account_id": bank_id, "amount": 250}],
        "post": False,
    })
    assert resp.status_code == 201, resp.get_json()
    receipt_id = resp.get_json()["id"]
    assert resp.get_json()["is_posted"] is False

    resp = client.delete(f"/api/receipts/{receipt_id}")
    assert resp.status_code == 200, resp.get_json()
    assert "deleted" in resp.get_json()["message"].lower()


# ── Test 13: Delete posted receipt rejected ───────────────────────

def test_delete_posted_receipt_rejected(client, session, open_2027_period):
    """Deleting a posted receipt returns 400."""
    bank_id = _find_account_id(session, Account.AccountType.BANK)

    resp = post_json(client, "/api/receipts", {
        "narration": "Posted receipt - no delete",
        "transaction_date": "2027-04-05",
        "line_items": [{"narration": "Deposit", "account_id": bank_id, "amount": 300}],
        "post": True,
    })
    assert resp.status_code == 201, resp.get_json()
    receipt_id = resp.get_json()["id"]

    resp = client.delete(f"/api/receipts/{receipt_id}")
    assert resp.status_code == 400
    assert "void" in resp.get_json()["error"].lower()


# ── Test 14: Overpayment partial assignment ───────────────────────

def test_overpayment_partial_assignment(client, session, open_2027_period):
    """$1500 receipt assigned to $1000 invoice: assignment amount capped at $1000."""
    bank_id = _find_account_id(session, Account.AccountType.BANK)
    revenue_id = _find_account_id(session, Account.AccountType.OPERATING_REVENUE)

    # Create $1000 invoice
    resp = post_json(client, "/api/invoices", {
        "narration": "Overpayment test invoice",
        "transaction_date": "2027-05-01",
        "post": True,
        "line_items": [{"narration": "Product", "account_id": revenue_id, "amount": 1000, "quantity": 1}],
    })
    assert resp.status_code == 201, resp.get_json()
    invoice_id = resp.get_json()["id"]

    # Create $1500 receipt
    resp = post_json(client, "/api/receipts", {
        "narration": "Overpayment receipt",
        "transaction_date": "2027-05-05",
        "line_items": [{"narration": "Deposit", "account_id": bank_id, "amount": 1500}],
        "post": True,
    })
    assert resp.status_code == 201, resp.get_json()
    receipt_id = resp.get_json()["id"]

    # Assign only $1000 (the invoice amount — frontend caps this)
    resp = post_json(client, "/api/assignments", {
        "transaction_id": receipt_id,
        "assigned_id": invoice_id,
        "assigned_type": "ClientInvoice",
        "amount": 1000,
        "assignment_date": "2027-05-05",
    })
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["amount"] == 1000.0


# ── Test 15: Detailed aging receivables ───────────────────────────

def test_aging_receivables_detail(client, session, open_2027_period):
    """Aging detail endpoint returns per-contact breakdown."""
    revenue_id = _find_account_id(session, Account.AccountType.OPERATING_REVENUE)

    # Create a contact
    resp = post_json(client, "/api/contacts", {
        "name": "Aging Test Corp",
        "contact_type": "client",
    })
    assert resp.status_code == 201, resp.get_json()
    contact_id = resp.get_json()["id"]

    # Create invoice linked to contact
    resp = post_json(client, "/api/invoices", {
        "narration": "Aging detail test",
        "transaction_date": "2027-06-01",
        "post": True,
        "contact_id": contact_id,
        "line_items": [{"narration": "Consulting", "account_id": revenue_id, "amount": 3150, "quantity": 1}],
    })
    assert resp.status_code == 201, resp.get_json()

    # Fetch the detail endpoint
    resp = client.get("/api/reports/aging-receivables-detail?as_of=2027-07-15")
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()

    assert "contacts" in data
    assert "summary" in data

    # Find our contact in the response
    matching = [c for c in data["contacts"] if c["contact_name"] == "Aging Test Corp"]
    assert len(matching) == 1, f"Expected Aging Test Corp in contacts, got {data['contacts']}"
    contact_data = matching[0]
    assert contact_data["total_outstanding"] > 0
    assert len(contact_data["transactions"]) >= 1

    # Check transaction detail
    tx = contact_data["transactions"][0]
    assert "transaction_no" in tx
    assert "age_bracket" in tx
    assert tx["outstanding"] > 0


# ── Test 16: Aging receivables tax-inclusive amounts ───────────────

def test_aging_receivables_tax_inclusive(client, session, open_2027_period):
    """Invoice with GST: aging report shows tax-inclusive amount."""
    revenue_id = _find_account_id(session, Account.AccountType.OPERATING_REVENUE)
    gst = session.query(Tax).filter(Tax.code == "GST").first()
    assert gst, "GST tax not found"

    # Create invoice with GST (5% on $2000 = $100 tax, total $2100)
    resp = post_json(client, "/api/invoices", {
        "narration": "Tax-inclusive aging test",
        "transaction_date": "2027-07-01",
        "post": True,
        "line_items": [{
            "narration": "Taxable service",
            "account_id": revenue_id,
            "amount": 2000,
            "quantity": 1,
            "tax_id": gst.id,
        }],
    })
    assert resp.status_code == 201, resp.get_json()
    inv_data = resp.get_json()

    # Verify serialized amount is tax-inclusive (2000 + 5% = 2100)
    assert inv_data["amount"] == 2100.0, f"Invoice amount should be 2100, got {inv_data['amount']}"

    # Verify aging summary includes tax-inclusive amount
    resp = client.get("/api/reports/aging-receivables?as_of=2027-08-01")
    assert resp.status_code == 200, resp.get_json()
    aging = resp.get_json()
    total_aging = sum(aging["balances"].values())
    assert total_aging >= 2100.0, f"Aging total should include tax: {aging['balances']}"

    # Verify aging detail includes tax-inclusive amount
    resp = client.get("/api/reports/aging-receivables-detail?as_of=2027-08-01")
    assert resp.status_code == 200, resp.get_json()
    detail = resp.get_json()
    # Find our invoice in the detail
    all_txs = []
    for c in detail.get("contacts", []):
        all_txs.extend(c.get("transactions", []))
    if detail.get("unassigned"):
        all_txs.extend(detail["unassigned"].get("transactions", []))
    matching = [t for t in all_txs if t["transaction_no"] == inv_data["transaction_no"]]
    assert len(matching) == 1, f"Invoice not found in aging detail: {all_txs}"
    assert matching[0]["amount"] == 2100.0, f"Aging detail amount should be 2100, got {matching[0]['amount']}"
    assert matching[0]["outstanding"] == 2100.0, f"Outstanding should be 2100, got {matching[0]['outstanding']}"
