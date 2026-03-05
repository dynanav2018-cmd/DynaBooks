"""Database and application configuration for DynaBooks."""

from backend.data_dir import get_db_path

DATABASE_URL = f"sqlite:///{get_db_path()}"

# Configure python-accounting BEFORE importing engine (import-order sensitive)
from python_accounting.config import config  # noqa: E402

config.configure_database(url=DATABASE_URL)

from python_accounting.database.engine import engine  # noqa: E402
from python_accounting.database.session import get_session  # noqa: E402
from python_accounting.models import Base  # noqa: E402


def init_db():
    """Create all database tables (python-accounting + custom)."""
    from backend.models import CustomBase
    from backend.models.contact import Contact  # noqa: F401
    from backend.models.product import Product  # noqa: F401
    from backend.models.transaction_contact import TransactionContact  # noqa: F401
    from backend.models.company_info import CompanyInfo  # noqa: F401
    from backend.models.recurring_journal import RecurringJournal  # noqa: F401
    from backend.models.bank_reconciliation import BankReconciliation, ReconciliationItem  # noqa: F401

    Base.metadata.create_all(engine)
    CustomBase.metadata.create_all(engine)

    # Run idempotent migrations for schema changes
    from backend.services.migrations import run_migrations, run_all_company_migrations
    run_migrations(engine)
    run_all_company_migrations()


def make_session():
    """Return a new accounting session.

    If the database already has an entity, sets session.entity automatically
    so that entity-isolated queries work immediately.
    """
    from python_accounting.models import Entity

    session = get_session(engine)
    entity = session.query(Entity).first()
    if entity:
        session.entity = entity
    return session
