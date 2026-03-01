"""Multi-company management: registry, engine cache, session factory."""

import json
import os
import re
from datetime import datetime

from sqlalchemy import create_engine

from python_accounting.database.session import get_session
from python_accounting.models import Base, Entity, Currency, Account, Tax

from backend.data_dir import (
    get_companies_file,
    get_company_db_path,
    get_company_dir,
)

# Cache of per-company SQLAlchemy engines
_engines = {}


def _load_registry():
    """Load companies.json registry. Returns list of company dicts."""
    path = get_companies_file()
    if not os.path.isfile(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


def _save_registry(companies):
    """Save companies list to companies.json."""
    path = get_companies_file()
    with open(path, "w") as f:
        json.dump(companies, f, indent=2)


def _slugify(name):
    """Convert a company name to a filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug or "company"


def list_companies():
    """Return all registered companies."""
    return _load_registry()


def get_company(slug):
    """Return a single company dict by slug, or None."""
    for c in _load_registry():
        if c["slug"] == slug:
            return c
    return None


def create_company(name, year_start=1, locale="en_CA"):
    """Create a new company with its own database.

    Returns the new company dict.
    """
    from backend.models import CustomBase
    from backend.models.contact import Contact  # noqa: F401
    from backend.models.product import Product  # noqa: F401
    from backend.models.transaction_contact import TransactionContact  # noqa: F401
    from backend.services.seeder import CHART_OF_ACCOUNTS

    slug = _slugify(name)
    registry = _load_registry()

    # Ensure unique slug
    existing_slugs = {c["slug"] for c in registry}
    base_slug = slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Create directory and database
    get_company_dir(slug)
    db_path = get_company_db_path(slug)
    db_url = f"sqlite:///{db_path}"

    eng = create_engine(db_url, echo=False).execution_options(
        include_deleted=False, ignore_isolation=False,
    )
    Base.metadata.create_all(eng)
    CustomBase.metadata.create_all(eng)

    # Seed entity, currency, chart of accounts, taxes
    session = get_session(eng)

    entity = Entity(name=name, year_start=year_start, locale=locale)
    session.add(entity)
    session.flush()

    cad = Currency(name="Canadian Dollar", code="CAD", entity_id=entity.id)
    session.add(cad)
    session.flush()
    entity.currency_id = cad.id
    session.commit()

    accounts_by_name = {}
    for acct_name, account_type, spec_code in CHART_OF_ACCOUNTS:
        account = Account(
            name=acct_name,
            account_type=account_type,
            currency_id=cad.id,
            entity_id=entity.id,
            description=f"Spec #{spec_code}",
        )
        session.add(account)
        session.flush()
        accounts_by_name[acct_name] = account
    session.commit()

    gst_account = accounts_by_name["GST/HST Payable"]
    gst = Tax(
        name="GST", code="GST", rate=5,
        account_id=gst_account.id, entity_id=entity.id,
    )
    session.add(gst)
    session.commit()
    session.close()

    # Cache the engine
    _engines[slug] = eng

    # Update registry
    company = {
        "slug": slug,
        "name": name,
        "year_start": year_start,
        "locale": locale,
        "created": datetime.now().isoformat(),
    }
    registry.append(company)
    _save_registry(registry)

    return company


def _is_default_company(slug):
    """Check if a slug refers to the default (non-multi-company) database."""
    registry = _load_registry()
    for c in registry:
        if c["slug"] == slug and c.get("default"):
            return True
    return False


def get_company_engine(slug):
    """Return (or create) a SQLAlchemy engine for the given company."""
    # Default company uses the main engine from config.py
    if _is_default_company(slug):
        from backend.config import engine
        return engine

    if slug in _engines:
        return _engines[slug]

    db_path = get_company_db_path(slug)
    if not os.path.isfile(db_path):
        raise ValueError(f"No database found for company '{slug}'")

    db_url = f"sqlite:///{db_path}"
    eng = create_engine(db_url, echo=False).execution_options(
        include_deleted=False, ignore_isolation=False,
    )
    _engines[slug] = eng
    return eng


def make_company_session(slug):
    """Create a session for the given company, with entity pre-set."""
    # Default company can use the standard make_session
    if _is_default_company(slug):
        from backend.config import make_session
        return make_session()

    eng = get_company_engine(slug)
    session = get_session(eng)
    entity = session.query(Entity).first()
    if entity:
        session.entity = entity
    return session
