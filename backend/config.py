"""Database and application configuration for DynaBooks."""

import os

# Resolve database path relative to the DynaBooks project root
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_db_path = os.path.join(_project_root, "dynabooks.db")
DATABASE_URL = f"sqlite:///{_db_path}"

# Configure python-accounting BEFORE importing engine (import-order sensitive)
from python_accounting.config import config  # noqa: E402

config.configure_database(url=DATABASE_URL)

from python_accounting.database.engine import engine  # noqa: E402
from python_accounting.database.session import get_session  # noqa: E402
from python_accounting.models import Base  # noqa: E402


def init_db():
    """Create all database tables (python-accounting + custom)."""
    from backend.models import CustomBase

    Base.metadata.create_all(engine)
    CustomBase.metadata.create_all(engine)


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
