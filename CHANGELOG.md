# DynaBooks Changelog

## March 6, 2026

### P&L / Income Statement PDF Fixes
- **Fixed missing account balances**: Income, Cost of Sales, and Expense accounts now show correct dollar amounts on the PDF (previously all showed $0.00)
- **Fixed Gross Profit calculation**: Now correctly computed as Income − Cost of Sales
- **Removed raw debug labels**: GROSS_PROFIT, TOTAL_REVENUE etc. no longer appear at the bottom of the report
- **Other Income section**: Shows with proper Total Other Income line
- **Expense accounts**: All expense accounts display on the P&L (including $0.00 ones) so users see their full chart of expenses
- **Income/COGS accounts**: Zero-balance accounts are hidden to keep the report clean

### COGS Journal & Post Atomicity Fix (Intermediate Only)
- Fixed "UNIQUE constraint failed: transaction.transaction_no" error when posting invoices with inventory items
- Root cause: orphaned COGS journal entries inflated the journal counter, causing duplicate transaction numbers
- `create_cogs_journal_entry` now auto-cleans orphaned COGS journals before creating new ones
- Fixed atomic post+inventory: if stock/COGS operations fail after `post()` commits, the invoice is automatically un-posted so it doesn't get stuck in a "posted but broken" state
- Same atomicity fix applied to Supplier Bills
- Previous fix for stale `cogs_journal_map` mappings retained and improved (now also deletes the associated journal)

### CSV Column Mapping Import Tool
- **Two-step import flow**: Upload a CSV file, then map arbitrary CSV columns to DynaBooks contact fields via dropdowns
- **Auto-matching**: Columns with names that match DynaBooks fields are pre-mapped automatically
- **Sample data preview**: Shows first 3 rows of data next to each column mapping
- **One-to-one enforcement**: Each DynaBooks field can only be mapped to one CSV column
- **Unmapped columns ignored**: Only mapped columns are imported; everything else is skipped
- **Backend**: New `POST /api/contacts/import/preview` endpoint; import endpoint accepts optional `column_map` JSON

## March 5, 2026

### Individual Tax Lines on Invoices & Bills
- Invoice and Bill detail views now show each tax separately (Tax 1 and Tax 2) with name and rate in the subtotal area
- PDF invoices and bills show individual tax lines with rate percentages
- Invoice and Bill forms display per-tax breakdown in the totals section

### Default Taxes on Contacts
- Added Default Tax 1 and Default Tax 2 fields to Client and Supplier records
- When creating an Invoice or Bill, line items auto-fill tax rates from the selected contact's defaults
- New line items added to an existing form also inherit the contact's default taxes
- Migration adds `default_tax_id` and `default_tax_id_2` columns to contacts table

### CSV Contact Import
- Import Clients and Suppliers from CSV files via the Contacts page
- Downloadable CSV template with all supported fields
- Optional contact type override (import all as Client, Supplier, or Both)
- Handles address data — creates Mailing Address records from CSV address fields

## Earlier Releases

### Dual-Tax Support
- Tax 2 system using hidden line items with `[TAX2:{id}:L{idx}]` narration pattern
- Tax 2 dropdown on each line item in Invoice and Bill forms
- Serializer merges Tax 2 amounts into tax summary when session is provided
- Expense-type tax creation bypasses library's Control-account validation

### Bank Reconciliation
- Bank reconciliation module: select account, set statement balance, check off cleared transactions
- Draft resume: reopen a saved reconciliation and continue where you left off
- Fixed SQL bugs in reconciliation queries

### Contact Revisions
- Company, website, and dual phone number fields with labels (Office, Cell, Home, Toll Free)
- Payment terms field (COD, Prepaid, 15 Days, 30 Days)
- Multiple address support per contact (Mailing, Office, Shipping, Home)
- Address migration from old single-address format to new multi-address table

### Inventory Module (Intermediate Only)
- Inventory tracking with weighted average cost (WAC)
- Stock movements: purchase, sale, adjustment, write-off
- Auto COGS journal entries on invoice posting (DR COGS / CR Inventory)
- Stock adjustment journals (DR Inventory / CR Inventory Adjustments, or DR Write-Off / CR Inventory)
- Purchase orders with supplier, line items, and status tracking
- Low stock alerts based on reorder point
- Inventory valuation report
- Preferred supplier field on products

### Account Editing
- Full account editing: Account Number, Type, and Category fields
- Account drill-in: view all ledger entries for any account

### Settings & Configuration
- Allow editing/deleting posted transactions (toggle in Settings)
- Multi-company support with company selector
- Company info: address, phone, email for PDF headers
- Logo upload for invoices and reports

### Reports
- Income Statement (Profit & Loss) with PDF export
- Balance Sheet with PDF export
- Aging Schedule (Receivables and Payables) with per-contact detail
- All reports show company header with logo and address

### Core Features
- Double-entry accounting via python-accounting library
- Client Invoices with auto-numbering (INV-YYYY-NNNN)
- Supplier Bills with supplier invoice reference
- Journal Entries (simple and compound)
- Bank Payments and Bank Receipts
- Transaction assignments (receipts to invoices, payments to bills)
- Recurring journal templates
- Auto-shutdown server when browser tab is closed
- System tray icon with single-instance enforcement
- Dropbox-friendly installation with portable data directory
