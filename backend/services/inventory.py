"""Core inventory logic: stock tracking, WAC, and COGS journal creation.

All stock updates flow through this module — routes never manipulate
stock_movements or product quantities directly.
"""

from datetime import datetime, timezone
from decimal import Decimal

from python_accounting.models import Account, LineItem
from python_accounting.transactions import JournalEntry

from backend.models.product import Product
from backend.models.stock_movement import StockMovement, CogsJournalMap


# ---------------------------------------------------------------------------
# Weighted average cost
# ---------------------------------------------------------------------------

def calculate_weighted_average_cost(
    existing_qty: Decimal,
    existing_avg_cost: Decimal,
    new_qty: Decimal,
    new_unit_cost: Decimal,
) -> Decimal:
    """Return the new weighted-average cost after receiving *new_qty* units."""
    total_qty = existing_qty + new_qty
    if total_qty <= 0:
        return Decimal("0")
    total_cost = (existing_qty * existing_avg_cost) + (new_qty * new_unit_cost)
    return (total_cost / total_qty).quantize(Decimal("0.0001"))


# ---------------------------------------------------------------------------
# Stock availability check
# ---------------------------------------------------------------------------

def check_stock_availability(session, inventory_line_items: list) -> list[str]:
    """Check that every inventory product has enough stock.

    *inventory_line_items* is a list of ``(line_item, product)`` tuples
    as returned by :func:`get_inventory_products_from_line_items`.

    Returns a list of human-readable error strings (empty → all OK).
    """
    # Aggregate quantities per product in case the same product appears
    # on multiple lines.
    qty_needed: dict[int, Decimal] = {}
    product_map: dict[int, Product] = {}
    for li, product in inventory_line_items:
        qty = Decimal(str(li.quantity)) * Decimal(str(li.amount or 0)) / Decimal(str(li.amount or 1))
        # Actually we just need the quantity field from the line item:
        qty = Decimal(str(li.quantity))
        qty_needed[product.id] = qty_needed.get(product.id, Decimal("0")) + qty
        product_map[product.id] = product

    errors = []
    for pid, needed in qty_needed.items():
        prod = product_map[pid]
        on_hand = Decimal(str(prod.quantity_on_hand or 0))
        if on_hand < needed:
            errors.append(
                f"Insufficient stock for {prod.name}: "
                f"{float(on_hand)} on hand, {float(needed)} required"
            )
    return errors


# ---------------------------------------------------------------------------
# Stock movement recording
# ---------------------------------------------------------------------------

def record_stock_purchase(
    session,
    product: Product,
    quantity: Decimal,
    unit_cost: Decimal,
    transaction_id: int | None = None,
    reference: str = "",
) -> StockMovement:
    """Record a stock increase from a bill/purchase posting."""
    old_qty = Decimal(str(product.quantity_on_hand or 0))
    old_cost = Decimal(str(product.average_cost or 0))

    new_avg = calculate_weighted_average_cost(old_qty, old_cost, quantity, unit_cost)
    new_qty = old_qty + quantity

    product.quantity_on_hand = new_qty
    product.average_cost = new_avg

    movement = StockMovement(
        product_id=product.id,
        transaction_id=transaction_id,
        movement_type="purchase",
        quantity_change=quantity,
        unit_cost=unit_cost,
        total_cost=quantity * unit_cost,
        quantity_after=new_qty,
        average_cost_after=new_avg,
        reference=reference,
        created_at=datetime.now(timezone.utc),
    )
    session.add(movement)
    session.flush()
    return movement


def record_stock_sale(
    session,
    product: Product,
    quantity: Decimal,
    transaction_id: int | None = None,
    reference: str = "",
) -> StockMovement:
    """Record a stock decrease from an invoice posting.

    Uses the current average_cost for valuation.  Does NOT create
    accounting entries — the caller is responsible for the COGS journal.
    """
    old_qty = Decimal(str(product.quantity_on_hand or 0))
    avg_cost = Decimal(str(product.average_cost or 0))
    new_qty = old_qty - quantity

    product.quantity_on_hand = new_qty
    # average_cost stays the same on sales

    movement = StockMovement(
        product_id=product.id,
        transaction_id=transaction_id,
        movement_type="sale",
        quantity_change=-quantity,
        unit_cost=avg_cost,
        total_cost=-(quantity * avg_cost),
        quantity_after=new_qty,
        average_cost_after=avg_cost,
        reference=reference,
        created_at=datetime.now(timezone.utc),
    )
    session.add(movement)
    session.flush()
    return movement


def record_stock_adjustment(
    session,
    product: Product,
    quantity_change: Decimal,
    unit_cost: Decimal | None = None,
    notes: str = "",
    reference: str = "",
) -> StockMovement:
    """Record a manual stock adjustment (positive or negative).

    For increases, *unit_cost* is required and WAC is recalculated.
    For decreases (write-offs), current average_cost is used.
    """
    old_qty = Decimal(str(product.quantity_on_hand or 0))
    old_cost = Decimal(str(product.average_cost or 0))

    if quantity_change > 0:
        if unit_cost is None:
            unit_cost = old_cost
        new_avg = calculate_weighted_average_cost(
            old_qty, old_cost, quantity_change, unit_cost
        )
    else:
        unit_cost = old_cost
        new_avg = old_cost

    new_qty = old_qty + quantity_change
    product.quantity_on_hand = new_qty
    product.average_cost = new_avg

    movement_type = "adjustment" if quantity_change > 0 else "write_off"
    movement = StockMovement(
        product_id=product.id,
        movement_type=movement_type,
        quantity_change=quantity_change,
        unit_cost=unit_cost,
        total_cost=quantity_change * unit_cost,
        quantity_after=new_qty,
        average_cost_after=new_avg,
        reference=reference,
        notes=notes,
        created_at=datetime.now(timezone.utc),
    )
    session.add(movement)
    session.flush()
    return movement


# ---------------------------------------------------------------------------
# Product-to-LineItem matching
# ---------------------------------------------------------------------------

def get_inventory_products_from_line_items(
    session, line_items
) -> list[tuple]:
    """Match line items to inventory-tracked products by narration.

    Returns a list of ``(line_item, product)`` tuples.
    """
    inventory_products = (
        session.query(Product)
        .filter(Product.track_inventory.is_(True), Product.is_active.is_(True))
        .all()
    )
    product_by_name = {p.name: p for p in inventory_products}

    matches = []
    for li in line_items:
        product = product_by_name.get(li.narration)
        if product:
            matches.append((li, product))
    return matches


# ---------------------------------------------------------------------------
# Auto COGS journal entry
# ---------------------------------------------------------------------------

def _next_journal_no(session, entity_id):
    """Generate the next unique journal transaction_no.

    The library's auto-numbering uses COUNT of existing journals which
    can collide when journals are deleted and gaps form.  Instead, find
    the highest existing number and increment it.
    """
    from sqlalchemy import text

    row = session.connection().execute(
        text(
            "SELECT MAX(CAST(SUBSTR(transaction_no, -4) AS INTEGER)) "
            'FROM "transaction" '
            "WHERE transaction_type = 'JOURNAL_ENTRY' "
            "AND entity_id = :eid"
        ),
        {"eid": entity_id},
    ).fetchone()
    max_num = (row[0] or 0) if row else 0

    # Extract period prefix from an existing journal, or use default
    prefix_row = session.connection().execute(
        text(
            "SELECT SUBSTR(transaction_no, 1, LENGTH(transaction_no) - 4) "
            'FROM "transaction" '
            "WHERE transaction_type = 'JOURNAL_ENTRY' "
            "AND entity_id = :eid LIMIT 1"
        ),
        {"eid": entity_id},
    ).fetchone()
    if prefix_row and prefix_row[0]:
        prefix = prefix_row[0]
    else:
        # Default: read from config
        from python_accounting.config import config
        prefix = config.transactions["types"]["JOURNAL_ENTRY"]["transaction_no_prefix"]
        prefix = f"{prefix}01/"

    return f"{prefix}{max_num + 1:04}"


def _cleanup_orphaned_cogs_journals(session):
    """Delete COGS journal entries that have no mapping in cogs_journal_map.

    These orphans can accumulate when invoice edits fail partway through,
    and they inflate the journal count causing transaction_no collisions.
    """
    from sqlalchemy import text

    orphan_ids = [
        row[0]
        for row in session.connection().execute(
            text(
                'SELECT t.id FROM "transaction" t '
                "LEFT JOIN cogs_journal_map m ON m.journal_transaction_id = t.id "
                "WHERE t.narration LIKE 'Auto COGS%' AND m.id IS NULL"
            )
        )
    ]
    if not orphan_ids:
        return

    conn = session.connection()
    for tid in orphan_ids:
        conn.execute(text("DELETE FROM ledger WHERE transaction_id = :tid"), {"tid": tid})
        conn.execute(text("DELETE FROM line_item WHERE transaction_id = :tid"), {"tid": tid})
        conn.execute(text('DELETE FROM "transaction" WHERE id = :tid'), {"tid": tid})
    # Clean recyclable entries for deleted ledger rows
    conn.execute(
        text(
            "DELETE FROM recyclable WHERE id NOT IN "
            "(SELECT id FROM ledger UNION SELECT id FROM line_item "
            'UNION SELECT id FROM "transaction")'
        )
    )
    session.flush()


def create_cogs_journal_entry(session, invoice_transaction, inventory_line_items):
    """Auto-create a compound JournalEntry: DR COGS / CR Inventory.

    *inventory_line_items* is a list of ``(line_item, product)`` tuples.
    Creates a single journal entry for the entire invoice and records
    the mapping in cogs_journal_map.
    """
    if not inventory_line_items:
        return None

    # Clean up any stale mapping from a previous post attempt
    existing = (
        session.query(CogsJournalMap)
        .filter(CogsJournalMap.invoice_transaction_id == invoice_transaction.id)
        .first()
    )
    if existing:
        # Also delete the associated journal transaction
        _delete_cogs_journal(session, existing.journal_transaction_id)
        session.delete(existing)
        session.flush()

    # Clean up orphaned COGS journals to prevent transaction_no collisions
    _cleanup_orphaned_cogs_journals(session)

    entity = session.entity

    # Build the COGS line item data
    all_lines = []
    for li, product in inventory_line_items:
        qty = Decimal(str(li.quantity))
        avg_cost = Decimal(str(product.average_cost or 0))
        cogs_amount = (qty * avg_cost).quantize(Decimal("0.0001"))

        if cogs_amount <= 0:
            continue

        # Debit COGS
        all_lines.append({
            "account_id": product.cogs_account_id,
            "amount": cogs_amount,
            "credited": False,
            "narration": f"COGS: {product.name} x {qty}",
        })
        # Credit Inventory
        all_lines.append({
            "account_id": product.inventory_account_id,
            "amount": cogs_amount,
            "credited": True,
            "narration": f"Inventory out: {product.name} x {qty}",
        })

    if not all_lines:
        return None

    # Use the _derive_main_account pattern from journals.py
    from backend.routes.journals import _derive_main_account
    account_id, main_credited, main_amount, remaining = _derive_main_account(all_lines)

    journal = JournalEntry(
        narration=f"Auto COGS for {invoice_transaction.transaction_no}",
        transaction_date=invoice_transaction.transaction_date,
        account_id=account_id,
        entity_id=entity.id,
        credited=main_credited,
    )
    journal.compound = True
    journal.main_account_amount = main_amount

    # Pre-assign a unique transaction_no to avoid collisions.
    # The library's auto-numbering uses COUNT which can collide with
    # existing numbers when journals have been deleted and recreated.
    journal.transaction_no = _next_journal_no(session, entity.id)

    session.add(journal)
    session.flush()

    persisted_lines = []
    for li_data in remaining:
        line = LineItem(
            narration=li_data.get("narration", ""),
            account_id=li_data["account_id"],
            amount=li_data["amount"],
            quantity=Decimal("1"),
            credited=li_data.get("credited", False),
            entity_id=entity.id,
        )
        session.add(line)
        session.flush()
        persisted_lines.append(line)

    for line in persisted_lines:
        journal.line_items.add(line)
    session.flush()

    journal.post(session)

    # Record the mapping so we can reverse later
    mapping = CogsJournalMap(
        invoice_transaction_id=invoice_transaction.id,
        journal_transaction_id=journal.id,
    )
    session.add(mapping)
    session.flush()

    return journal


# ---------------------------------------------------------------------------
# Reversal (un-post support)
# ---------------------------------------------------------------------------

def reverse_stock_movements(session, transaction_id: int):
    """Reverse all stock movements for a transaction.

    Called when a posted invoice or bill is un-posted.
    Restores product quantities and average costs to their prior state.
    """
    movements = (
        session.query(StockMovement)
        .filter(StockMovement.transaction_id == transaction_id)
        .order_by(StockMovement.id.desc())
        .all()
    )
    for mv in movements:
        product = session.query(Product).get(mv.product_id)
        if not product:
            continue
        # Undo the quantity change
        product.quantity_on_hand = Decimal(str(product.quantity_on_hand or 0)) - mv.quantity_change
        # Restore the average cost that existed before this movement
        # The simplest correct approach: recalculate from the movement
        # before this one, or fall back to 0.
        prev_movement = (
            session.query(StockMovement)
            .filter(
                StockMovement.product_id == mv.product_id,
                StockMovement.id < mv.id,
            )
            .order_by(StockMovement.id.desc())
            .first()
        )
        if prev_movement:
            product.average_cost = prev_movement.average_cost_after
        else:
            product.average_cost = Decimal("0")

        session.delete(mv)

    session.flush()


def _delete_cogs_journal(session, journal_id: int):
    """Delete a COGS journal transaction and its ledger/line_item rows."""
    from sqlalchemy import text

    conn = session.connection()
    conn.execute(
        text("DELETE FROM ledger WHERE transaction_id = :tid"),
        {"tid": journal_id},
    )
    conn.execute(
        text("DELETE FROM line_item WHERE transaction_id = :tid"),
        {"tid": journal_id},
    )
    journal = session.get(JournalEntry, journal_id)
    if journal:
        session.delete(journal)
    else:
        # Fallback: delete via raw SQL if ORM can't find it
        conn.execute(
            text('DELETE FROM "transaction" WHERE id = :tid'),
            {"tid": journal_id},
        )


def reverse_cogs_journal(session, invoice_transaction_id: int):
    """Delete the auto-created COGS journal for an invoice."""
    mapping = (
        session.query(CogsJournalMap)
        .filter(CogsJournalMap.invoice_transaction_id == invoice_transaction_id)
        .first()
    )
    if not mapping:
        return

    _delete_cogs_journal(session, mapping.journal_transaction_id)
    session.delete(mapping)
    session.flush()
