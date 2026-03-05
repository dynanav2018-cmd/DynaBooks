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


def _add_account_if_missing(conn, name, account_type, description):
    """Insert an account if one with the same name does not already exist.

    python-accounting uses table inheritance: each Account row needs a
    matching ``recyclable`` row (with the same ``id``).  We insert into
    ``recyclable`` first to obtain the correct id.
    """
    row = conn.execute(
        text("SELECT id FROM account WHERE name = :n"),
        {"n": name},
    ).fetchone()
    if row:
        return
    # Get entity_id and currency_id from the first entity
    entity_row = conn.execute(text(
        "SELECT id, currency_id FROM entity LIMIT 1"
    )).fetchone()
    if not entity_row:
        return
    # Auto-generate the next account_code for this account_type
    max_code_row = conn.execute(
        text("SELECT MAX(account_code) FROM account WHERE account_type = :atype"),
        {"atype": account_type},
    ).fetchone()
    next_code = (max_code_row[0] or 0) + 1 if max_code_row and max_code_row[0] else 1

    # Insert recyclable parent row first (table inheritance)
    conn.execute(text(
        "INSERT INTO recyclable (recycled_type, created_at, updated_at)"
        " VALUES ('Account', datetime('now'), datetime('now'))"
    ))
    new_id = conn.execute(text("SELECT last_insert_rowid()")).fetchone()[0]

    conn.execute(text(
        "INSERT INTO account (id, name, account_type, description,"
        " account_code, currency_id, entity_id)"
        " VALUES (:id, :name, :atype, :desc, :code, :cid, :eid)"
    ), {
        "id": new_id,
        "name": name,
        "atype": account_type,
        "desc": description,
        "code": next_code,
        "cid": entity_row[1],
        "eid": entity_row[0],
    })


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

        # CompanyInfo: add allow_edit_posted column
        if _table_exists(insp, "company_info"):
            if not _column_exists(insp, "company_info", "allow_edit_posted"):
                conn.execute(text(
                    "ALTER TABLE company_info ADD COLUMN allow_edit_posted BOOLEAN NOT NULL DEFAULT 0"
                ))

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

        # Products table: add inventory tracking columns
        if "products" in tables:
            for col, col_def in [
                ("sku", "VARCHAR(100)"),
                ("track_inventory", "BOOLEAN NOT NULL DEFAULT 0"),
                ("quantity_on_hand", "NUMERIC(13, 4) NOT NULL DEFAULT 0"),
                ("reorder_point", "NUMERIC(13, 4) NOT NULL DEFAULT 0"),
                ("average_cost", "NUMERIC(13, 4) NOT NULL DEFAULT 0"),
                ("inventory_account_id", "INTEGER"),
                ("cogs_account_id", "INTEGER"),
                ("preferred_supplier_id", "INTEGER"),
            ]:
                if not _column_exists(insp, "products", col):
                    conn.execute(text(
                        f"ALTER TABLE products ADD COLUMN {col} {col_def}"
                    ))

        # Stock movements table
        if not _table_exists(insp, "stock_movements"):
            conn.execute(text("""
                CREATE TABLE stock_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    transaction_id INTEGER,
                    purchase_order_id INTEGER,
                    movement_type VARCHAR(30) NOT NULL,
                    quantity_change NUMERIC(13, 4) NOT NULL,
                    unit_cost NUMERIC(13, 4) NOT NULL,
                    total_cost NUMERIC(13, 4) NOT NULL,
                    quantity_after NUMERIC(13, 4) NOT NULL,
                    average_cost_after NUMERIC(13, 4) NOT NULL,
                    reference VARCHAR(255),
                    notes TEXT,
                    created_at DATETIME
                )
            """))

        # COGS journal mapping table
        if not _table_exists(insp, "cogs_journal_map"):
            conn.execute(text("""
                CREATE TABLE cogs_journal_map (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_transaction_id INTEGER NOT NULL UNIQUE,
                    journal_transaction_id INTEGER NOT NULL
                )
            """))

        # Purchase orders table
        if not _table_exists(insp, "purchase_orders"):
            conn.execute(text("""
                CREATE TABLE purchase_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    po_number VARCHAR(50) NOT NULL UNIQUE,
                    supplier_contact_id INTEGER NOT NULL,
                    order_date DATE NOT NULL,
                    expected_date DATE,
                    status VARCHAR(20) NOT NULL DEFAULT 'draft',
                    notes TEXT,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))

        # Purchase order lines table
        if not _table_exists(insp, "purchase_order_lines"):
            conn.execute(text("""
                CREATE TABLE purchase_order_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase_order_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    description VARCHAR(255),
                    quantity_ordered NUMERIC(13, 4) NOT NULL,
                    quantity_received NUMERIC(13, 4) NOT NULL DEFAULT 0,
                    unit_cost NUMERIC(13, 4) NOT NULL,
                    tax_id INTEGER
                )
            """))

        # Fix Inventory account type: NON_CURRENT_ASSET -> INVENTORY
        if "account" in tables:
            conn.execute(text(
                "UPDATE account SET account_type = 'INVENTORY'"
                " WHERE name = 'Inventory'"
                " AND account_type = 'NON_CURRENT_ASSET'"
            ))

        # Add missing accounts for inventory module
        if "account" in tables:
            _add_account_if_missing(conn, "Inventory Adjustments",
                                    "NON_OPERATING_REVENUE", "Spec #4910")
            _add_account_if_missing(conn, "Inventory Write-Off",
                                    "DIRECT_EXPENSE", "Spec #5010")

        # Contact table: add company, website, phone fields, payment_terms
        if "contacts" in tables:
            for col, col_def in [
                ("company", "VARCHAR(255)"),
                ("website", "VARCHAR(255)"),
                ("phone_1", "VARCHAR(50)"),
                ("phone_1_label", "VARCHAR(20)"),
                ("phone_2", "VARCHAR(50)"),
                ("phone_2_label", "VARCHAR(20)"),
                ("payment_terms", "VARCHAR(20) DEFAULT '30 Days'"),
            ]:
                if not _column_exists(insp, "contacts", col):
                    conn.execute(text(
                        f"ALTER TABLE contacts ADD COLUMN {col} {col_def}"
                    ))

            # Migrate existing phone data to phone_1
            if _column_exists(insp, "contacts", "phone_1"):
                conn.execute(text(
                    "UPDATE contacts SET phone_1 = phone, phone_1_label = 'Office'"
                    " WHERE phone IS NOT NULL AND phone != ''"
                    " AND (phone_1 IS NULL OR phone_1 = '')"
                ))

            # Migrate payment_terms_days to payment_terms string
            if _column_exists(insp, "contacts", "payment_terms"):
                conn.execute(text(
                    "UPDATE contacts SET payment_terms = '30 Days'"
                    " WHERE payment_terms IS NULL"
                    " AND payment_terms_days = 30"
                ))
                conn.execute(text(
                    "UPDATE contacts SET payment_terms = '15 Days'"
                    " WHERE payment_terms IS NULL"
                    " AND payment_terms_days = 15"
                ))

        # Contact table: add default tax columns
        if "contacts" in tables:
            for col, col_def in [
                ("default_tax_id", "INTEGER"),
                ("default_tax_id_2", "INTEGER"),
            ]:
                if not _column_exists(insp, "contacts", col):
                    conn.execute(text(
                        f"ALTER TABLE contacts ADD COLUMN {col} {col_def}"
                    ))

        # Contact addresses table: create if missing
        if not _table_exists(insp, "contact_addresses"):
            conn.execute(text("""
                CREATE TABLE contact_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_id INTEGER NOT NULL,
                    address_type VARCHAR(30) NOT NULL DEFAULT 'Address',
                    address_line_1 VARCHAR(500),
                    address_line_2 VARCHAR(500),
                    city VARCHAR(255),
                    province_state VARCHAR(255),
                    postal_code VARCHAR(20),
                    country VARCHAR(100),
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))

            # Migrate existing contact address data into contact_addresses
            if "contacts" in tables:
                conn.execute(text("""
                    INSERT INTO contact_addresses
                        (contact_id, address_type, address_line_1, address_line_2,
                         city, province_state, postal_code, country,
                         created_at, updated_at)
                    SELECT id, 'Mailing Address', address_line_1, address_line_2,
                           city, province_state, postal_code, country,
                           created_at, updated_at
                    FROM contacts
                    WHERE address_line_1 IS NOT NULL AND address_line_1 != ''
                """))

        # Transaction addresses table (billing/shipping for invoices/bills)
        if not _table_exists(insp, "transaction_addresses"):
            conn.execute(text("""
                CREATE TABLE transaction_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id INTEGER NOT NULL UNIQUE,
                    billing_address_id INTEGER,
                    shipping_address_id INTEGER
                )
            """))

        # Bank reconciliation tables
        if not _table_exists(insp, "bank_reconciliations"):
            conn.execute(text("""
                CREATE TABLE bank_reconciliations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    period_year INTEGER NOT NULL,
                    period_month INTEGER NOT NULL,
                    statement_balance NUMERIC(13, 4) DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'draft',
                    completed_at DATETIME,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))

        if not _table_exists(insp, "reconciliation_items"):
            conn.execute(text("""
                CREATE TABLE reconciliation_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reconciliation_id INTEGER NOT NULL,
                    ledger_id INTEGER NOT NULL,
                    is_cleared BOOLEAN DEFAULT 0
                )
            """))

        # Fix account names: replace double hyphens with em dashes
        if "account" in tables:
            for old, new in [
                ("Product Sales -- Gps Systems", "Product Sales — Gps Systems"),
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
