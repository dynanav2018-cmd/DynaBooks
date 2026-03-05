"""Inventory management routes: stock levels, adjustments, valuation."""

from decimal import Decimal

from flask import Blueprint, g, jsonify, request
from python_accounting.models import Account

from backend.models.product import Product
from backend.models.stock_movement import StockMovement
from backend.serializers import serialize_product, serialize_stock_movement
from backend.services.inventory import record_stock_adjustment

bp = Blueprint("inventory", __name__, url_prefix="/api")


@bp.route("/inventory", methods=["GET"])
def list_inventory():
    """List all active products (inventory-tracked and sales-only)."""
    products = (
        g.session.query(Product)
        .filter(Product.is_active.is_(True))
        .all()
    )
    return jsonify([serialize_product(p) for p in products])


@bp.route("/inventory/<int:product_id>", methods=["GET"])
def get_inventory_product(product_id):
    product = g.session.get(Product, product_id)
    if not product:
        return jsonify(error="Product not found"), 404
    return jsonify(serialize_product(product))


@bp.route("/inventory/<int:product_id>/movements", methods=["GET"])
def get_stock_movements(product_id):
    """Stock movement history for a product."""
    product = g.session.get(Product, product_id)
    if not product:
        return jsonify(error="Product not found"), 404

    movements = (
        g.session.query(StockMovement)
        .filter(StockMovement.product_id == product_id)
        .order_by(StockMovement.id.desc())
        .all()
    )
    return jsonify([serialize_stock_movement(m) for m in movements])


@bp.route("/inventory/low-stock", methods=["GET"])
def low_stock():
    """Products at or below their reorder point."""
    products = (
        g.session.query(Product)
        .filter(
            Product.track_inventory.is_(True),
            Product.is_active.is_(True),
            Product.quantity_on_hand <= Product.reorder_point,
        )
        .all()
    )
    return jsonify([serialize_product(p) for p in products])


@bp.route("/inventory/adjustment", methods=["POST"])
def create_adjustment():
    """Create a stock adjustment (increase or decrease/write-off).

    Also auto-creates a journal entry:
    - Increase: DR Inventory / CR Inventory Adjustments
    - Decrease: DR Inventory Write-Off / CR Inventory
    """
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    product_id = data.get("product_id")
    quantity_change = data.get("quantity_change")
    notes = data.get("notes", "")

    if not product_id or quantity_change is None:
        return jsonify(error="product_id and quantity_change are required"), 400

    quantity_change = Decimal(str(quantity_change))
    if quantity_change == 0:
        return jsonify(error="quantity_change cannot be zero"), 400

    product = g.session.get(Product, product_id)
    if not product or not product.track_inventory:
        return jsonify(error="Product not found or not inventory-tracked"), 404

    # Block negative stock
    if quantity_change < 0:
        on_hand = Decimal(str(product.quantity_on_hand or 0))
        if on_hand + quantity_change < 0:
            return jsonify(
                error=f"Cannot adjust below zero: {float(on_hand)} on hand"
            ), 400

    unit_cost_input = data.get("unit_cost")
    unit_cost = Decimal(str(unit_cost_input)) if unit_cost_input else None

    try:
        movement = record_stock_adjustment(
            g.session, product, quantity_change,
            unit_cost=unit_cost, notes=notes,
            reference=f"Manual adjustment",
        )

        # Auto-create the journal entry
        _create_adjustment_journal(
            g.session, product, quantity_change, movement.unit_cost, notes
        )

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_stock_movement(movement)), 201


@bp.route("/inventory/valuation", methods=["GET"])
def inventory_valuation():
    """Total inventory valuation: sum of qty * avg_cost per product."""
    products = (
        g.session.query(Product)
        .filter(Product.track_inventory.is_(True), Product.is_active.is_(True))
        .all()
    )
    items = []
    total = Decimal("0")
    for p in products:
        qty = Decimal(str(p.quantity_on_hand or 0))
        cost = Decimal(str(p.average_cost or 0))
        value = qty * cost
        total += value
        items.append({
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "quantity_on_hand": float(qty),
            "average_cost": float(cost),
            "total_value": float(value),
        })
    return jsonify({"items": items, "total_value": float(total)})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_adjustment_journal(session, product, quantity_change, unit_cost, notes):
    """Create a JournalEntry for a stock adjustment."""
    from python_accounting.models import LineItem
    from python_accounting.transactions import JournalEntry
    from backend.routes.journals import _derive_main_account

    entity = session.entity
    amount = abs(quantity_change * unit_cost).quantize(Decimal("0.0001"))
    if amount <= 0:
        return

    # Find the adjustment/write-off accounts
    if quantity_change > 0:
        # Increase: DR Inventory / CR Inventory Adjustments
        lines_data = [
            {
                "account_id": product.inventory_account_id,
                "amount": amount,
                "credited": False,
                "narration": f"Stock adjustment: {product.name} +{quantity_change}",
            },
            {
                "account_id": _get_account_id_by_name(session, "Inventory Adjustments"),
                "amount": amount,
                "credited": True,
                "narration": f"Stock adjustment: {product.name} +{quantity_change}",
            },
        ]
    else:
        # Decrease/Write-off: DR Inventory Write-Off / CR Inventory
        lines_data = [
            {
                "account_id": _get_account_id_by_name(session, "Inventory Write-Off"),
                "amount": amount,
                "credited": False,
                "narration": f"Stock write-off: {product.name} {quantity_change}",
            },
            {
                "account_id": product.inventory_account_id,
                "amount": amount,
                "credited": True,
                "narration": f"Stock write-off: {product.name} {quantity_change}",
            },
        ]

    account_id, main_credited, main_amount, remaining = _derive_main_account(lines_data)

    from datetime import datetime
    journal = JournalEntry(
        narration=notes or f"Stock adjustment: {product.name}",
        transaction_date=datetime.now(),
        account_id=account_id,
        entity_id=entity.id,
        credited=main_credited,
    )
    journal.compound = True
    journal.main_account_amount = main_amount

    session.add(journal)
    session.flush()

    persisted = []
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
        persisted.append(line)

    for line in persisted:
        journal.line_items.add(line)
    session.flush()

    journal.post(session)


def _get_account_id_by_name(session, name):
    """Look up an account ID by name."""
    account = session.query(Account).filter(Account.name == name).first()
    if account:
        return account.id
    return None
