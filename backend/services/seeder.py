"""Seed the DynaBooks database with entity, chart of accounts, and tax rates."""

from python_accounting.models import Entity, Currency, Account, Tax

from backend.config import init_db, make_session

# Chart of accounts: (name, AccountType, spec_account_number)
CHART_OF_ACCOUNTS = [
    # Assets
    ("Petty Cash", Account.AccountType.BANK, "1000"),
    ("Operating Bank Account", Account.AccountType.BANK, "1010"),
    ("USD Bank Account", Account.AccountType.BANK, "1020"),
    ("Accounts Receivable", Account.AccountType.RECEIVABLE, "1100"),
    ("Prepaid Expenses", Account.AccountType.NON_CURRENT_ASSET, "1200"),
    ("Inventory", Account.AccountType.INVENTORY, "1300"),
    ("Equipment", Account.AccountType.NON_CURRENT_ASSET, "1500"),
    # Contra Asset
    ("Accumulated Depreciation", Account.AccountType.CONTRA_ASSET, "1510"),
    # Liabilities
    ("Accounts Payable", Account.AccountType.PAYABLE, "2000"),
    ("GST/HST Payable", Account.AccountType.CONTROL, "2100"),
    ("Accrued Liabilities", Account.AccountType.NON_CURRENT_LIABILITY, "2200"),
    ("Credit Card Payable", Account.AccountType.PAYABLE, "2300"),
    # Equity
    ("Owner's Equity", Account.AccountType.EQUITY, "3000"),
    ("Retained Earnings", Account.AccountType.EQUITY, "3100"),
    # Revenue
    ("Product Sales — GPS Systems", Account.AccountType.OPERATING_REVENUE, "4000"),
    ("Product Sales — Accessories", Account.AccountType.OPERATING_REVENUE, "4010"),
    ("Service Revenue — Subscriptions", Account.AccountType.OPERATING_REVENUE, "4020"),
    ("Service Revenue — Support", Account.AccountType.OPERATING_REVENUE, "4030"),
    ("Shipping Revenue", Account.AccountType.OPERATING_REVENUE, "4100"),
    ("Other Income", Account.AccountType.NON_OPERATING_REVENUE, "4900"),
    ("Inventory Adjustments", Account.AccountType.NON_OPERATING_REVENUE, "4910"),
    # Expenses
    ("Cost of Goods Sold", Account.AccountType.DIRECT_EXPENSE, "5000"),
    ("Inventory Write-Off", Account.AccountType.DIRECT_EXPENSE, "5010"),
    ("Shipping Expense", Account.AccountType.OPERATING_EXPENSE, "5100"),
    ("Salaries & Wages", Account.AccountType.OPERATING_EXPENSE, "6000"),
    ("Rent", Account.AccountType.OPERATING_EXPENSE, "6100"),
    ("Utilities", Account.AccountType.OPERATING_EXPENSE, "6200"),
    ("Office Supplies", Account.AccountType.OPERATING_EXPENSE, "6300"),
    ("Insurance", Account.AccountType.OPERATING_EXPENSE, "6400"),
    ("Professional Fees", Account.AccountType.OPERATING_EXPENSE, "6500"),
    ("Travel & Entertainment", Account.AccountType.OPERATING_EXPENSE, "6600"),
    ("Marketing & Advertising", Account.AccountType.OPERATING_EXPENSE, "6700"),
    ("Depreciation Expense", Account.AccountType.OPERATING_EXPENSE, "6800"),
    ("Bank Fees & Interest", Account.AccountType.OPERATING_EXPENSE, "6900"),
    ("Miscellaneous Expense", Account.AccountType.OPERATING_EXPENSE, "7000"),
]


def seed():
    """Seed the database with DynaNav Systems entity, accounts, and taxes.

    Idempotent: skips seeding if entity already exists.
    """
    init_db()
    session = make_session()

    # Check if already seeded
    existing = session.query(Entity).first()
    if existing:
        print("Database already seeded. Skipping.")
        session.close()
        return

    # 1. Create Entity (this sets session.entity via event listener)
    entity = Entity(name="DynaNav Systems Inc.", year_start=1, locale="en_CA")
    session.add(entity)
    session.flush()

    # 2. Create Currency (needs entity_id)
    cad = Currency(name="Canadian Dollar", code="CAD", entity_id=entity.id)
    session.add(cad)
    session.flush()

    # 3. Link currency back to entity
    entity.currency_id = cad.id
    session.commit()

    # 4. Create Chart of Accounts
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

    # 5. Create GST Tax (linked to GST/HST Payable control account)
    gst_account = accounts_by_name["GST/HST Payable"]
    gst = Tax(
        name="GST",
        code="GST",
        rate=5,
        account_id=gst_account.id,
        entity_id=entity.id,
    )
    session.add(gst)
    session.commit()

    # Summary
    account_count = session.query(Account).count()
    tax_count = session.query(Tax).count()
    print(f"Seeded: Entity='{entity.name}', Currency={cad.code}, "
          f"Accounts={account_count}, Taxes={tax_count}")
    session.close()


if __name__ == "__main__":
    seed()
