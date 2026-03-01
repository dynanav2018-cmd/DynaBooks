"""Idempotent schema migrations for DynaBooks.

Called from init_db() after create_all() to add columns that were
introduced after the initial schema was deployed.
"""

from sqlalchemy import inspect, text


def _column_exists(inspector, table_name, column_name):
    """Check if a column exists in a table."""
    try:
        columns = inspector.get_columns(table_name)
        return any(c["name"] == column_name for c in columns)
    except Exception:
        return False


def _column_is_not_null(inspector, table_name, column_name):
    """Check if a column has a NOT NULL constraint."""
    try:
        columns = inspector.get_columns(table_name)
        for c in columns:
            if c["name"] == column_name:
                return c.get("nullable") is False
    except Exception:
        pass
    return False


def _table_exists(inspector, table_name):
    """Check if a table exists."""
    return table_name in inspector.get_table_names()


def run_migrations(engine):
    """Run all idempotent migrations."""
    insp = inspect(engine)

    # Check which tables exist
    tables = insp.get_table_names()

    with engine.connect() as conn:
        # Contact table: add city, province_state, postal_code
        if "contacts" in tables:
            if not _column_exists(insp, "contacts", "city"):
                conn.execute(text(
                    "ALTER TABLE contacts ADD COLUMN city VARCHAR(255)"
                ))
            if not _column_exists(insp, "contacts", "province_state"):
                conn.execute(text(
                    "ALTER TABLE contacts ADD COLUMN province_state VARCHAR(255)"
                ))
            if not _column_exists(insp, "contacts", "postal_code"):
                conn.execute(text(
                    "ALTER TABLE contacts ADD COLUMN postal_code VARCHAR(20)"
                ))

        # Product table: add product_type, expense_account_id
        if "products" in tables:
            if not _column_exists(insp, "products", "product_type"):
                conn.execute(text(
                    "ALTER TABLE products ADD COLUMN product_type VARCHAR(20) DEFAULT 'product'"
                ))
            if not _column_exists(insp, "products", "expense_account_id"):
                conn.execute(text(
                    "ALTER TABLE products ADD COLUMN expense_account_id INTEGER"
                ))

            # Fix revenue_account_id NOT NULL -> nullable (SQLite requires table rebuild)
            if _column_is_not_null(insp, "products", "revenue_account_id"):
                conn.execute(text("""
                    CREATE TABLE products_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        default_price NUMERIC(13, 4) NOT NULL DEFAULT 0,
                        product_type VARCHAR(20) DEFAULT 'product',
                        revenue_account_id INTEGER,
                        expense_account_id INTEGER,
                        tax_id INTEGER,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                """))
                conn.execute(text("""
                    INSERT INTO products_new
                        (id, name, description, default_price, product_type,
                         revenue_account_id, expense_account_id, tax_id,
                         is_active, created_at, updated_at)
                    SELECT id, name, description, default_price,
                           COALESCE(product_type, 'product'),
                           revenue_account_id, expense_account_id, tax_id,
                           is_active, created_at, updated_at
                    FROM products
                """))
                conn.execute(text("DROP TABLE products"))
                conn.execute(text("ALTER TABLE products_new RENAME TO products"))

        # CompanyInfo table: create if missing
        if not _table_exists(insp, "company_info"):
            conn.execute(text("""
                CREATE TABLE company_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER UNIQUE,
                    address_line_1 VARCHAR(500),
                    address_line_2 VARCHAR(500),
                    city VARCHAR(255),
                    province_state VARCHAR(255),
                    postal_code VARCHAR(20),
                    country VARCHAR(100),
                    phone VARCHAR(50),
                    email VARCHAR(255)
                )
            """))

        # RecurringJournals table: create if missing
        if not _table_exists(insp, "recurring_journals"):
            conn.execute(text("""
                CREATE TABLE recurring_journals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL,
                    narration VARCHAR(255),
                    account_id INTEGER,
                    line_items_json TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))

        # RecurringJournals: make account_id nullable (was NOT NULL)
        if _table_exists(insp, "recurring_journals"):
            if _column_is_not_null(insp, "recurring_journals", "account_id"):
                conn.execute(text("""
                    CREATE TABLE recurring_journals_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        narration VARCHAR(255),
                        account_id INTEGER,
                        line_items_json TEXT NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                """))
                conn.execute(text("""
                    INSERT INTO recurring_journals_new
                        (id, name, narration, account_id, line_items_json,
                         is_active, created_at, updated_at)
                    SELECT id, name, narration, account_id, line_items_json,
                           is_active, created_at, updated_at
                    FROM recurring_journals
                """))
                conn.execute(text("DROP TABLE recurring_journals"))
                conn.execute(text(
                    "ALTER TABLE recurring_journals_new"
                    " RENAME TO recurring_journals"
                ))

        # TransactionContacts table: create if missing
        if not _table_exists(insp, "transaction_contacts"):
            conn.execute(text("""
                CREATE TABLE transaction_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id INTEGER NOT NULL,
                    contact_id INTEGER NOT NULL,
                    UNIQUE(transaction_id)
                )
            """))

        # Fix account names: replace double hyphens with em dashes
        if "account" in tables:
            for old, new in [
                ("Product Sales -- GPS Systems", "Product Sales — GPS Systems"),
                ("Product Sales -- Accessories", "Product Sales — Accessories"),
                ("Service Revenue -- Subscriptions", "Service Revenue — Subscriptions"),
                ("Service Revenue -- Support", "Service Revenue — Support"),
            ]:
                conn.execute(
                    text("UPDATE account SET name = :new WHERE name = :old"),
                    {"old": old, "new": new},
                )

        conn.commit()


def run_all_company_migrations():
    """Run migrations on all company databases."""
    import os
    from backend.data_dir import get_companies_file

    companies_file = get_companies_file()
    if not os.path.isfile(companies_file):
        return

    import json
    with open(companies_file, "r") as f:
        companies = json.load(f)

    for company in companies:
        slug = company.get("slug")
        if not slug or company.get("default"):
            # Default company is handled by init_db()
            continue

        from backend.data_dir import get_company_db_path
        db_path = get_company_db_path(slug)
        if not os.path.isfile(db_path):
            continue

        from sqlalchemy import create_engine
        eng = create_engine(f"sqlite:///{db_path}", echo=False)
        try:
            run_migrations(eng)
        except Exception:
            pass  # Skip broken company databases
        finally:
            eng.dispose()
