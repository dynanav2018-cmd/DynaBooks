# DynaBooks Development Document

**Project:** DynaBooks Accounting System
**Developer:** DynaNav Systems Inc.
**Platform:** Windows 10/11 Desktop Application
**Version:** 1.0 (February 2026)

---

## 1. Overview

DynaBooks is a self-hosted, double-entry accounting system built for small business use. It runs as a standalone Windows desktop application with a web-based user interface served locally. The application supports multi-company management, invoice and bill tracking, bank receipts and payments, journal entries, financial reporting, PDF generation, and year-end closing.

All accounting data is stored locally in SQLite databases, and the application can be deployed to a shared Dropbox folder so it can be run from any computer with access to that folder.

---

## 2. Technology Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| **Backend** | Python 3.13 + Flask | REST API on localhost |
| **Accounting Engine** | python-accounting 1.0.0 | Double-entry ledger, transaction posting, reports |
| **Database** | SQLite via SQLAlchemy | One database per company |
| **Frontend** | React 19 + Tailwind CSS v4 | Single-page application |
| **Build Tool** | Vite 7.3 | Frontend bundling |
| **PDF Generation** | xhtml2pdf + Jinja2 | Invoice and report PDFs |
| **Desktop Packaging** | PyInstaller 6.16 | Standalone Windows EXE |
| **System Tray** | pystray + Pillow | Tray icon with menu |
| **Currency** | CAD (Canadian Dollar) | Configurable per entity |

---

## 3. Application Architecture

### 3.1 How It Runs

When the user launches `DynaBooks.exe`:

1. The launcher initializes the database schema and seeds default data if needed
2. A free TCP port is found on the local machine
3. A Flask web server starts on `http://127.0.0.1:<port>`
4. The default browser opens to that address
5. A system tray icon appears (navy blue with white "D") with options to open the browser or quit

The React frontend is pre-built and served as static files by Flask. All API calls go to `/api/*` endpoints on the same server.

### 3.2 Directory Structure

```
DynaBooks/                      (application root)
+-- DynaBooks.exe               (launcher)
+-- install.bat                 (installer/updater script)
+-- _internal/                  (PyInstaller bundled dependencies)
|   +-- frontend/dist/          (built React app)
|   +-- backend/templates/      (PDF Jinja2 templates)
|   +-- config.toml             (python-accounting config)
|   +-- python313.dll           (Python runtime)
|   +-- ...                     (all Python packages)
+-- dist_data/                  (clean default company template)
|   +-- dynabooks.db            (My Company - 33 accounts, GST)
|   +-- companies.json          (empty registry)
|   +-- logos/                  (empty)
+-- data/                       (live accounting data - syncs via Dropbox)
    +-- dynabooks.db            (default company database)
    +-- companies.json          (multi-company registry)
    +-- logos/
    |   +-- logo.png            (company logo)
    +-- <company-slug>/         (additional company directories)
        +-- dynabooks.db
        +-- logos/
            +-- logo.png
```

### 3.3 Source Code Layout

```
DynaBooks/                      (project root)
+-- backend/
|   +-- app.py                  (Flask app factory, session management)
|   +-- config.py               (database URL, init_db, make_session)
|   +-- data_dir.py             (data directory resolution)
|   +-- company_manager.py      (multi-company create/list/session)
|   +-- serializers.py          (model-to-JSON serialization)
|   +-- models/
|   |   +-- __init__.py         (CustomBase declaration)
|   |   +-- contact.py          (Client/Supplier contacts)
|   |   +-- product.py          (Product catalog)
|   |   +-- transaction_contact.py (transaction-contact link)
|   +-- routes/
|   |   +-- accounts.py         (Chart of Accounts CRUD)
|   |   +-- invoices.py         (Client Invoice CRUD + post)
|   |   +-- bills.py            (Supplier Bill CRUD + post)
|   |   +-- banking.py          (Receipts, Payments, Void)
|   |   +-- journals.py         (Journal Entry CRUD + post)
|   |   +-- contacts.py         (Contact CRUD)
|   |   +-- reports.py          (Financial reports)
|   |   +-- pdf.py              (PDF generation)
|   |   +-- dashboard.py        (Dashboard metrics)
|   |   +-- companies.py        (Multi-company management)
|   |   +-- company.py          (Company settings + logo)
|   |   +-- closing.py          (Year-end close)
|   |   +-- assignments.py      (Receipt/payment to invoice/bill)
|   |   +-- products.py         (Product catalog CRUD)
|   |   +-- taxes.py            (Tax rate CRUD)
|   +-- services/
|   |   +-- seeder.py           (Chart of accounts + GST seed data)
|   |   +-- closing.py          (Year-end close logic)
|   +-- templates/
|   |   +-- invoice_pdf.html    (Invoice/Bill PDF template)
|   |   +-- report_pdf.html     (Financial report PDF template)
|   +-- tests/
|       +-- test_phase1.py      (7 tests - entity, accounts, tax)
|       +-- test_phase2.py      (13 tests - API endpoints)
|       +-- test_phase3.py      (7 tests - PDF, frontend)
|       +-- test_phase4.py      (9 tests - banking, contacts)
|       +-- test_phase5.py      (17 tests - multi-company, closing, void)
+-- frontend/
|   +-- package.json
|   +-- vite.config.js
|   +-- src/
|       +-- App.jsx             (Router + providers)
|       +-- main.jsx            (Entry point)
|       +-- index.css           (Tailwind + brand colors)
|       +-- api/                (API client modules)
|       +-- components/
|       |   +-- layout/         (AppShell, Sidebar, TopBar)
|       |   +-- shared/         (Button, Modal, DataTable, etc.)
|       +-- hooks/              (useApi, useToast, useCompany)
|       +-- pages/              (all page components)
|       +-- utils/              (formatting helpers)
+-- dynabooks_launcher.py       (EXE entry point)
+-- dynabooks.spec              (PyInstaller build config)
+-- install.bat                 (installer source)
+-- create_clean_data.py        (generates dist_data/)
```

---

## 4. Features

### 4.1 Dashboard

The home screen displays key financial metrics at a glance:

- **Cash Balance** -- total across all bank accounts
- **Accounts Receivable** -- outstanding customer invoices
- **Accounts Payable** -- outstanding supplier bills
- **Revenue This Month** -- from the income statement
- **Expenses This Month** -- from the income statement
- **Net Income This Month** -- revenue minus expenses

### 4.2 Sales (Invoices)

- Create client invoices with multiple line items
- Each line item has: description, revenue account, quantity, unit price, tax
- Product selector auto-fills line item fields from the product catalog
- Save as draft or post immediately to the ledger
- View invoice details with line items, tax breakdown, and totals
- Edit draft invoice narration
- Delete unposted drafts
- Generate PDF invoices with company logo

### 4.3 Purchases (Bills)

- Create supplier bills with multiple line items
- Each line item has: description, expense account, quantity, price, tax
- Product selector for quick entry
- Save as draft or post to ledger
- View, edit, delete (same rules as invoices)
- Generate PDF bills

### 4.4 Banking

**Client Receipts:**
- Record payments received from clients
- Select bank account (destination) and receivable account
- Assign receipt to a specific invoice
- Overpayment handling: if receipt exceeds invoice amount, the assignment is capped at the invoice amount; the excess remains as unassigned credit
- Void posted receipts (creates a reversing journal entry and removes assignments)
- Delete unposted draft receipts

**Supplier Payments:**
- Record payments made to suppliers
- Select bank account (source) and payable account
- Assign payment to a specific bill
- Same overpayment and void/delete logic as receipts

### 4.5 Journal Entries

- Create manual journal entries with debit and credit lines
- Entries must balance (total debits = total credits)
- Post to the ledger
- Delete unposted drafts
- Used internally by the void and year-end close features

### 4.6 Contacts

- Manage clients and suppliers
- Fields: name, contact type (client/supplier), email, phone, address
- Activity tracking: total invoiced/billed, total paid, outstanding balance
- Contacts appear in invoice, bill, and banking dropdowns

### 4.7 Chart of Accounts

33 pre-configured accounts across all standard categories:

| Category | Accounts |
|----------|----------|
| **Bank** | Petty Cash, Operating Bank Account, USD Bank Account |
| **Receivable** | Accounts Receivable |
| **Other Assets** | Prepaid Expenses, Inventory, Equipment |
| **Contra Asset** | Accumulated Depreciation |
| **Payable** | Accounts Payable, Credit Card Payable |
| **Control** | GST/HST Payable |
| **Other Liabilities** | Accrued Liabilities |
| **Equity** | Owner's Equity, Retained Earnings |
| **Revenue** | Product Sales (GPS, Accessories), Service Revenue (Subscriptions, Support), Shipping Revenue, Other Income |
| **Expenses** | COGS, Shipping, Salaries, Rent, Utilities, Office Supplies, Insurance, Professional Fees, Travel, Marketing, Depreciation, Bank Fees, Miscellaneous |

### 4.8 Financial Reports

All reports support date range filtering and PDF export:

| Report | Description |
|--------|-------------|
| **Income Statement** | Revenue and expenses for a date range, with net income |
| **Balance Sheet** | Assets, liabilities, and equity as of a specific date |
| **Trial Balance** | All account balances to verify debits equal credits |
| **Cashflow Statement** | Cash inflows and outflows by category |
| **Aging Receivables** | Outstanding invoices grouped by age (Current, 31-90, 91-180, 181-365, 365+ days) with per-client detail |
| **Aging Payables** | Outstanding bills grouped by age with per-vendor detail |

The aging reports include both a summary view (totals by age bracket) and a detailed view (individual transactions grouped by contact).

### 4.9 Settings

**Company Tab:**
- Company name (rename "My Company" to your business name)
- Locale setting
- Logo upload (PNG or JPG, max 2 MB) -- displayed on invoices and reports

**Taxes Tab:**
- Create, edit, delete tax rates
- Default: GST at 5% linked to GST/HST Payable control account
- Each tax has: name, code, rate (%), control account

**Products Tab:**
- Product/service catalog for quick entry on invoices and bills
- Each product has: name, description, default price, revenue account, tax
- When selected on an invoice, auto-fills description, account, price, and tax

### 4.10 Multi-Company Support

- Create unlimited companies, each with its own database
- Each company gets a full chart of accounts, currency, and GST tax
- Switch between companies via the company selector
- API requests routed to the correct database via `X-Company` header
- Company data stored in separate subdirectories within the data folder

### 4.11 Year-End Closing

- Preview shows all revenue and expense accounts with balances
- Closing creates journal entries to transfer all revenue/expense balances to Retained Earnings
- Revenue accounts are debited (zeroed out)
- Expense accounts are credited (zeroed out)
- Reporting period is marked as CLOSED
- Prevents accidental re-closing

### 4.12 PDF Generation

Two PDF templates powered by xhtml2pdf + Jinja2:

**Invoice/Bill PDF:**
- Company name and logo (base64 embedded)
- Invoice/bill number, date, and status
- Customer/supplier contact details
- Line items table with description, quantity, unit price, amount
- Tax breakdown, subtotal, and grand total

**Report PDF:**
- Company name and logo
- Report title and date range
- Formatted financial data tables
- Aging detail with per-contact transaction listings

---

## 5. API Reference

### 5.1 Endpoints Summary

All endpoints are prefixed with `/api/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /dashboard | Dashboard metrics |
| GET | /accounts | List accounts (optional type filter) |
| POST | /accounts | Create account |
| PUT | /accounts/:id | Update account |
| DELETE | /accounts/:id | Delete account |
| GET | /invoices | List invoices |
| GET | /invoices/:id | Get invoice detail |
| POST | /invoices | Create invoice |
| PUT | /invoices/:id | Update invoice |
| DELETE | /invoices/:id | Delete unposted invoice |
| POST | /invoices/:id/post | Post invoice to ledger |
| GET | /invoices/:id/pdf | Download invoice PDF |
| GET | /bills | List bills |
| GET | /bills/:id | Get bill detail |
| POST | /bills | Create bill |
| PUT | /bills/:id | Update bill |
| DELETE | /bills/:id | Delete unposted bill |
| POST | /bills/:id/post | Post bill to ledger |
| GET | /bills/:id/pdf | Download bill PDF |
| GET | /receipts | List client receipts |
| POST | /receipts | Create receipt |
| DELETE | /receipts/:id | Delete unposted receipt |
| POST | /receipts/:id/void | Void posted receipt |
| GET | /payments | List supplier payments |
| POST | /payments | Create payment |
| DELETE | /payments/:id | Delete unposted payment |
| POST | /payments/:id/void | Void posted payment |
| POST | /assignments | Assign receipt to invoice or payment to bill |
| GET | /journals | List journal entries |
| POST | /journals | Create journal entry |
| DELETE | /journals/:id | Delete unposted entry |
| POST | /journals/:id/post | Post journal entry |
| GET | /contacts | List contacts (optional type filter) |
| POST | /contacts | Create contact |
| PUT | /contacts/:id | Update contact |
| DELETE | /contacts/:id | Delete contact |
| GET | /products | List products |
| POST | /products | Create product |
| PUT | /products/:id | Update product |
| DELETE | /products/:id | Deactivate product |
| GET | /taxes | List tax rates |
| POST | /taxes | Create tax rate |
| PUT | /taxes/:id | Update tax rate |
| DELETE | /taxes/:id | Delete tax rate |
| GET | /company | Get company entity info |
| PUT | /company | Update company name/locale |
| POST | /company/logo | Upload company logo |
| GET | /company/logo | Get company logo |
| GET | /companies | List all companies |
| POST | /companies | Create new company |
| GET | /companies/:slug | Get company details |
| GET | /reports/income-statement | Income statement (from, to) |
| GET | /reports/balance-sheet | Balance sheet (as_of) |
| GET | /reports/trial-balance | Trial balance (as_of) |
| GET | /reports/cashflow | Cashflow statement (from, to) |
| GET | /reports/aging-receivables | Aging receivables summary |
| GET | /reports/aging-payables | Aging payables summary |
| GET | /reports/aging-receivables-detail | Aging receivables by contact |
| GET | /reports/aging-payables-detail | Aging payables by contact |
| GET | /reports/:type/pdf | Download report PDF |
| GET | /closing/preview | Year-end close preview |
| POST | /closing | Execute year-end close |

---

## 6. User Interface

### 6.1 Navigation

The sidebar organizes features into groups:

- **Dashboard** -- home screen with financial overview
- **Sales**
  - Invoices
  - Clients
- **Purchases**
  - Bills
  - Suppliers
- **Accounting**
  - Journal Entries
  - Chart of Accounts
  - Year-End Close
- **Banking** -- receipts and payments
- **Reports** -- all financial reports
- **Settings** -- company, taxes, products

### 6.2 Brand Colors

| Element | Color | Hex |
|---------|-------|-----|
| Navy (primary) | Dark blue | #1B3A5C |
| Accent | Medium blue | #2E75B6 |
| Background | Light gray | Tailwind defaults |
| Cards | White | #FFFFFF |

---

## 7. Database

### 7.1 Engine

SQLite via SQLAlchemy. The python-accounting library provides the ORM models for all accounting entities (Entity, Currency, Account, Tax, LineItem, Transaction types, Assignments, ReportingPeriod).

Custom models added for DynaBooks:
- **Contact** -- client and supplier records
- **Product** -- product/service catalog
- **TransactionContact** -- links transactions to contacts

### 7.2 Key Constraints

- Transaction dates must not fall exactly on a reporting period start date
- Line items must be `session.add()` + `session.flush()` before adding to `transaction.line_items`
- Account names are auto-title-cased by the library (e.g., "GPS" becomes "Gps")
- Account codes are auto-generated from config base codes; specification numbers are stored in the `description` field
- Journal entries must balance (total debits = total credits)
- Posted transactions cannot be deleted; they must be voided instead

---

## 8. Installation and Deployment

### 8.1 Installation Package Contents

The distribution folder contains:

| File/Folder | Purpose |
|-------------|---------|
| `DynaBooks.exe` | Application launcher |
| `install.bat` | Installer and updater script |
| `_internal/` | Python runtime, libraries, frontend, templates |
| `dist_data/` | Clean default company database template |

### 8.2 First-Time Installation

1. Copy the `DynaBooks` folder to any location (or share it)
2. Run `install.bat`
3. The script auto-detects the Dropbox folder location
4. Choose the install directory (default: `<Dropbox>\DynaBooks`)
5. The script copies application files and sets up the default "My Company" data
6. A desktop shortcut is created

### 8.3 Updating

1. Build the new version (frontend + EXE)
2. Run `install.bat` again pointing to the same directory
3. The script detects the existing installation
4. Application files (`DynaBooks.exe` + `_internal/`) are replaced
5. The `data/` directory is **not touched** -- all accounting data is preserved

### 8.4 Dropbox Deployment

When installed to a Dropbox folder:
- The application and data sync across all computers with Dropbox access
- Each computer runs the same EXE from the synced folder
- Run `install.bat` on each computer to create a local desktop shortcut
- Only one computer should run DynaBooks at a time (SQLite limitation)

### 8.5 Data Directory

The `data/` folder stores all accounting data:
- `dynabooks.db` -- main company database
- `companies.json` -- registry of additional companies
- `logos/logo.png` -- company logo
- `<slug>/` -- subdirectories for additional companies

When running as an EXE, data is stored next to the executable. This allows Dropbox to sync both application and data together.

---

## 9. Development Workflow

### 9.1 Prerequisites

- Python 3.13 with pip
- Node.js LTS with npm
- python-accounting==1.0.0
- Flask, xhtml2pdf, pystray, Pillow

### 9.2 Development Mode

**Backend** (port 5000):
```
cd DynaBooks
flask run
```

**Frontend** (port 5173, proxies API to :5000):
```
cd DynaBooks/frontend
npm run dev
```

### 9.3 Build Process

**1. Build frontend:**
```
cd frontend
npm run build
```

**2. Generate clean data (if needed):**
```
python create_clean_data.py
```

**3. Build EXE:**
```
python -m PyInstaller dynabooks.spec --noconfirm
```

The spec file automatically copies `install.bat` and `dist_data/` into the dist folder after the build.

**4. Deploy:**
```
Run dist\DynaBooks\install.bat
```

### 9.4 Testing

```
python -m pytest backend/tests/ -v
```

53 tests across 5 test files covering:
- Phase 1: Entity, currency, chart of accounts, tax setup
- Phase 2: Flask API endpoints, serialization, CRUD operations
- Phase 3: PDF generation, frontend build verification
- Phase 4: Banking, contacts, assignments
- Phase 5: Multi-company, year-end closing, void transactions, data directory, aging reports

---

## 10. Development Phases

### Phase 1 -- Foundation
- Entity and currency creation (DynaNav Systems Inc., CAD)
- Chart of accounts (33 accounts across all categories)
- GST tax rate (5%) linked to control account
- Database seeder with idempotent initialization
- 7 tests

### Phase 2 -- REST API
- Flask application with Blueprint-based routing
- Full CRUD for accounts, invoices, bills, journal entries
- Transaction posting workflow (create, add line items, post)
- Contact and tax management endpoints
- JSON serialization for all models
- 12 tests (19 total)

### Phase 3 -- Frontend and PDF
- React 19 + Tailwind CSS v4 single-page application
- Vite build tool with Dropbox-safe cache directory
- All page components: dashboard, invoices, bills, journals, banking, contacts, reports, settings
- Responsive sidebar navigation with grouped menu items
- xhtml2pdf-based PDF generation for invoices and reports
- Jinja2 templates with company logo support
- 6 tests (25 total)

### Phase 4 -- Banking and Contacts
- Client receipts and supplier payments
- Assignment of receipts to invoices and payments to bills
- Contact activity tracking (invoiced, paid, outstanding)
- Product catalog with default pricing
- Product selector on invoice and bill forms
- 9 tests (34 total)

### Phase 5 -- Production Readiness
- Configurable data directory (EXE-relative for Dropbox deployment)
- Company logo upload and display on PDFs
- Year-end closing with journal entries and period locking
- Multi-company support (separate databases, slug-based routing, company selector UI)
- PyInstaller EXE packaging with system tray icon
- Desktop installer batch script with Dropbox auto-detection
- Clean default company data for fresh installations
- 9 tests (42 total)

### Phase 5.1 -- Refinements
- Void posted receipts and payments (reversing journal entries)
- Delete unposted draft receipts and payments
- Overpayment handling (cap assignment at invoice/bill amount)
- Detailed aging reports grouped by contact
- Tax rate display fixes (whole-number percentage throughout)
- Product selector on invoice and bill line items
- Data directory moved to EXE-relative for Dropbox sharing
- Installation package with clean default company
- 11 tests (53 total)

---

## 11. Known Considerations

1. **Single-user access**: SQLite does not support concurrent writes from multiple machines. Only one computer should run DynaBooks at a time when sharing via Dropbox.

2. **Account naming**: The python-accounting library auto-title-cases account names. "GPS" becomes "Gps" in the database. Specification account numbers are stored in the description field instead.

3. **Transaction dates**: Dates must not fall exactly on a reporting period start date (January 1 when year_start=1) or the library raises an error.

4. **Vite cache**: The frontend build cache must be stored outside Dropbox to avoid EBUSY file lock errors. This is configured in `vite.config.js`.

5. **Import order**: `config.configure_database()` must be called before importing the engine module. Custom models must be imported before `create_all()`.
