"""Generate a clean data directory with one default company for distribution."""

import json
import os
import shutil
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure python-accounting with a temporary URL (we'll use our own engine)
from python_accounting.config import config
config.configure_database(url="sqlite:///temp_unused.db")

from python_accounting.models import Base, Entity, Currency, Account, Tax
from sqlalchemy import create_engine
from python_accounting.database.session import get_session

from backend.models import CustomBase
from backend.models.contact import Contact, ContactAddress, TransactionAddress  # noqa: F401
from backend.models.bank_reconciliation import BankReconciliation, ReconciliationItem  # noqa: F401
from backend.models.product import Product  # noqa: F401
from backend.models.transaction_contact import TransactionContact  # noqa: F401
from backend.models.company_info import CompanyInfo  # noqa: F401
from backend.models.recurring_journal import RecurringJournal  # noqa: F401
from backend.models.stock_movement import StockMovement, CogsJournalMap  # noqa: F401
from backend.models.purchase_order import PurchaseOrder, PurchaseOrderLine  # noqa: F401
from backend.services.seeder import CHART_OF_ACCOUNTS

DIST_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist_data")


def create_clean_data():
    """Create a clean data directory at dist_data/ with one default company."""

    # Wipe and recreate
    if os.path.exists(DIST_DATA):
        shutil.rmtree(DIST_DATA)
    os.makedirs(DIST_DATA)
    os.makedirs(os.path.join(DIST_DATA, "logos"), exist_ok=True)

    # Empty companies registry
    with open(os.path.join(DIST_DATA, "companies.json"), "w") as f:
        json.dump([], f)

    # Create fresh database
    db_path = os.path.join(DIST_DATA, "dynabooks.db")
    db_url = f"sqlite:///{db_path}"
    eng = create_engine(db_url, echo=False).execution_options(
        include_deleted=False, ignore_isolation=False,
    )
    Base.metadata.create_all(eng)
    CustomBase.metadata.create_all(eng)

    session = get_session(eng)

    # Entity -- generic name the user will rename in Settings
    entity = Entity(name="My Company", year_start=1, locale="en_CA")
    session.add(entity)
    session.flush()

    # Currency
    cad = Currency(name="Canadian Dollar", code="CAD", entity_id=entity.id)
    session.add(cad)
    session.flush()
    entity.currency_id = cad.id
    session.commit()

    # Chart of Accounts
    accounts_by_name = {}
    for name, account_type, spec_code in CHART_OF_ACCOUNTS:
        account = Account(
            name=name,
            account_type=account_type,
            currency_id=cad.id,
            entity_id=entity.id,
            description=f"Spec #{spec_code}",
        )
        session.add(account)
        session.flush()
        accounts_by_name[name] = account
    session.commit()

    # GST Tax
    gst_account = accounts_by_name["GST/HST Payable"]
    gst = Tax(
        name="GST", code="GST", rate=5,
        account_id=gst_account.id, entity_id=entity.id,
    )
    session.add(gst)
    session.commit()

    account_count = session.query(Account).count()
    tax_count = session.query(Tax).count()
    session.close()

    # Run migrations to add any extra columns/tables/accounts
    from backend.services.migrations import run_migrations
    run_migrations(eng)

    # Clean up temp file if it was created
    if os.path.exists("temp_unused.db"):
        os.remove("temp_unused.db")

    print(f"Clean data created at: {DIST_DATA}")
    print(f"  Entity: My Company")
    print(f"  Currency: CAD")
    print(f"  Accounts: {account_count}")
    print(f"  Taxes: {tax_count} (GST 5%)")
    print(f"  Companies registry: empty (default company uses main DB)")


if __name__ == "__main__":
    create_clean_data()
