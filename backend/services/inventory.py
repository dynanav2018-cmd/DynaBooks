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

def create_cogs_journal_entry(session, invoice_transaction, inventory_line_items):
    """Auto-create a compound JournalEntry: DR COGS / CR Inventory.

    *inventory_line_items* is a list of ``(line_item, product)`` tuples.
    Creates a single journal entry for the entire invoice and records
    the mapping in cogs_journal_map.
    """
    if not inventory_line_items:
        return None

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


def reverse_cogs_journal(session, invoice_transaction_id: int):
    """Delete the auto-created COGS journal for an invoice."""
    from sqlalchemy import text

    mapping = (
        session.query(CogsJournalMap)
        .filter(CogsJournalMap.invoice_transaction_id == invoice_transaction_id)
        .first()
    )
    if not mapping:
        return

    journal_id = mapping.journal_transaction_id

    # Delete ledger entries, line items, and the journal itself via raw SQL
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

    session.delete(mapping)
    session.flush()
