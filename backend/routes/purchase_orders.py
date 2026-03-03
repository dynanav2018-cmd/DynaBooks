"""Purchase Order routes."""

from datetime import datetime, date
from decimal import Decimal

from flask import Blueprint, g, jsonify, request

from backend.models.product import Product
from backend.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from backend.models.contact import Contact
from backend.serializers import serialize_purchase_order, serialize_purchase_order_line

bp = Blueprint("purchase_orders", __name__, url_prefix="/api")


def _next_po_number(session):
    """Generate the next PO number: PO-YYYY-NNNN."""
    import datetime as dt
    year = dt.date.today().year
    prefix = f"PO-{year}-"
    last = (
        session.query(PurchaseOrder)
        .filter(PurchaseOrder.po_number.like(f"{prefix}%"))
        .order_by(PurchaseOrder.id.desc())
        .first()
    )
    if last:
        seq = int(last.po_number.split("-")[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


@bp.route("/purchase-orders", methods=["GET"])
def list_purchase_orders():
    query = g.session.query(PurchaseOrder).order_by(PurchaseOrder.id.desc())
    status = request.args.get("status")
    if status:
        query = query.filter(PurchaseOrder.status == status)
    pos = query.all()
    result = []
    for po in pos:
        lines = (
            g.session.query(PurchaseOrderLine)
            .filter(PurchaseOrderLine.purchase_order_id == po.id)
            .all()
        )
        data = serialize_purchase_order(po, lines)
        # Attach supplier name
        contact = g.session.get(Contact, po.supplier_contact_id)
        data["supplier_name"] = contact.name if contact else None
        result.append(data)
    return jsonify(result)


@bp.route("/purchase-orders/<int:po_id>", methods=["GET"])
def get_purchase_order(po_id):
    po = g.session.get(PurchaseOrder, po_id)
    if not po:
        return jsonify(error="Purchase order not found"), 404
    lines = (
        g.session.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.purchase_order_id == po.id)
        .all()
    )
    data = serialize_purchase_order(po, lines)
    contact = g.session.get(Contact, po.supplier_contact_id)
    data["supplier_name"] = contact.name if contact else None
    # Enrich lines with product names
    for line_data, line_obj in zip(data["lines"], lines):
        product = g.session.get(Product, line_obj.product_id)
        line_data["product_name"] = product.name if product else None
    return jsonify(data)


@bp.route("/purchase-orders", methods=["POST"])
def create_purchase_order():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    supplier_id = data.get("supplier_contact_id")
    if not supplier_id:
        return jsonify(error="supplier_contact_id is required"), 400

    lines_data = data.get("lines", [])
    if not lines_data:
        return jsonify(error="At least one line is required"), 400

    order_date = data.get("order_date")
    if not order_date:
        return jsonify(error="order_date is required"), 400

    try:
        po = PurchaseOrder(
            po_number=_next_po_number(g.session),
            supplier_contact_id=int(supplier_id),
            order_date=date.fromisoformat(order_date),
            expected_date=(
                date.fromisoformat(data["expected_date"])
                if data.get("expected_date") else None
            ),
            status="draft",
            notes=data.get("notes"),
        )
        g.session.add(po)
        g.session.flush()

        for ld in lines_data:
            line = PurchaseOrderLine(
                purchase_order_id=po.id,
                product_id=int(ld["product_id"]),
                description=ld.get("description", ""),
                quantity_ordered=Decimal(str(ld["quantity_ordered"])),
                unit_cost=Decimal(str(ld["unit_cost"])),
                tax_id=ld.get("tax_id"),
            )
            g.session.add(line)
        g.session.flush()

        # If send=true, mark as sent immediately
        if data.get("send"):
            po.status = "sent"

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    lines = (
        g.session.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.purchase_order_id == po.id)
        .all()
    )
    return jsonify(serialize_purchase_order(po, lines)), 201


@bp.route("/purchase-orders/<int:po_id>", methods=["PUT"])
def update_purchase_order(po_id):
    po = g.session.get(PurchaseOrder, po_id)
    if not po:
        return jsonify(error="Purchase order not found"), 404
    if po.status not in ("draft", "sent"):
        return jsonify(error="Can only edit draft or sent purchase orders"), 400

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    try:
        if "supplier_contact_id" in data:
            po.supplier_contact_id = int(data["supplier_contact_id"])
        if "order_date" in data:
            po.order_date = date.fromisoformat(data["order_date"])
        if "expected_date" in data:
            po.expected_date = (
                date.fromisoformat(data["expected_date"])
                if data["expected_date"] else None
            )
        if "notes" in data:
            po.notes = data["notes"]

        # Replace lines if provided
        lines_data = data.get("lines")
        if lines_data is not None:
            # Delete existing lines
            g.session.query(PurchaseOrderLine).filter(
                PurchaseOrderLine.purchase_order_id == po.id
            ).delete()
            g.session.flush()

            for ld in lines_data:
                line = PurchaseOrderLine(
                    purchase_order_id=po.id,
                    product_id=int(ld["product_id"]),
                    description=ld.get("description", ""),
                    quantity_ordered=Decimal(str(ld["quantity_ordered"])),
                    unit_cost=Decimal(str(ld["unit_cost"])),
                    tax_id=ld.get("tax_id"),
                )
                g.session.add(line)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    lines = (
        g.session.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.purchase_order_id == po.id)
        .all()
    )
    return jsonify(serialize_purchase_order(po, lines))


@bp.route("/purchase-orders/<int:po_id>", methods=["DELETE"])
def delete_purchase_order(po_id):
    po = g.session.get(PurchaseOrder, po_id)
    if not po:
        return jsonify(error="Purchase order not found"), 404
    if po.status != "draft":
        return jsonify(error="Can only delete draft purchase orders"), 400

    try:
        g.session.query(PurchaseOrderLine).filter(
            PurchaseOrderLine.purchase_order_id == po.id
        ).delete()
        g.session.delete(po)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Purchase order deleted"), 200


@bp.route("/purchase-orders/<int:po_id>/send", methods=["POST"])
def send_purchase_order(po_id):
    po = g.session.get(PurchaseOrder, po_id)
    if not po:
        return jsonify(error="Purchase order not found"), 404
    if po.status != "draft":
        return jsonify(error="Can only send draft purchase orders"), 400

    po.status = "sent"
    g.session.commit()

    lines = (
        g.session.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.purchase_order_id == po.id)
        .all()
    )
    return jsonify(serialize_purchase_order(po, lines))


@bp.route("/purchase-orders/<int:po_id>/receive", methods=["POST"])
def receive_purchase_order(po_id):
    """Receive goods against a PO and auto-create a SupplierBill."""
    po = g.session.get(PurchaseOrder, po_id)
    if not po:
        return jsonify(error="Purchase order not found"), 404
    if po.status not in ("sent", "partial"):
        return jsonify(error="Can only receive sent or partial purchase orders"), 400

    data = request.get_json() or {}
    received_quantities = data.get("received_quantities", {})

    lines = (
        g.session.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.purchase_order_id == po.id)
        .all()
    )

    try:
        bill_line_items = []
        any_received = False

        for line in lines:
            qty_str = received_quantities.get(str(line.id))
            if qty_str is None:
                # Default: receive remaining quantity
                qty_to_receive = line.quantity_ordered - line.quantity_received
            else:
                qty_to_receive = Decimal(str(qty_str))

            if qty_to_receive <= 0:
                continue

            remaining = line.quantity_ordered - line.quantity_received
            if qty_to_receive > remaining:
                return jsonify(
                    error=f"Cannot receive {qty_to_receive} for line {line.id}; "
                          f"only {remaining} remaining"
                ), 400

            line.quantity_received += qty_to_receive
            any_received = True

            product = g.session.get(Product, line.product_id)
            bill_line_items.append({
                "narration": product.name if product else line.description or "",
                "account_id": product.inventory_account_id if product else None,
                "quantity": qty_to_receive,
                "amount": line.unit_cost,
                "tax_id": line.tax_id,
            })

        if not any_received:
            return jsonify(error="No quantities to receive"), 400

        # Check if fully or partially received
        all_received = all(
            l.quantity_received >= l.quantity_ordered for l in lines
        )
        po.status = "received" if all_received else "partial"

        # Auto-create a SupplierBill
        bill_id = _create_bill_from_po(g.session, po, bill_line_items)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    result = serialize_purchase_order(po, lines)
    result["bill_id"] = bill_id
    return jsonify(result)


@bp.route("/purchase-orders/<int:po_id>/cancel", methods=["POST"])
def cancel_purchase_order(po_id):
    po = g.session.get(PurchaseOrder, po_id)
    if not po:
        return jsonify(error="Purchase order not found"), 404
    if po.status in ("received", "cancelled"):
        return jsonify(error="Cannot cancel this purchase order"), 400

    po.status = "cancelled"
    g.session.commit()

    lines = (
        g.session.query(PurchaseOrderLine)
        .filter(PurchaseOrderLine.purchase_order_id == po.id)
        .all()
    )
    return jsonify(serialize_purchase_order(po, lines))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_bill_from_po(session, po, line_items_data):
    """Create a draft SupplierBill from received PO lines.

    Follows the exact same pattern as backend/routes/bills.py create_bill().
    """
    from python_accounting.models import Account, LineItem
    from python_accounting.transactions import SupplierBill
    from backend.models.transaction_contact import TransactionContact

    entity = session.entity

    # Find the payable account (main account for bills)
    payable = (
        session.query(Account)
        .filter(Account.account_type == Account.AccountType.PAYABLE)
        .first()
    )
    if not payable:
        raise ValueError("No Payable account found")

    bill = SupplierBill(
        narration=f"Purchase from PO {po.po_number}",
        transaction_date=datetime.now(),
        account_id=payable.id,
        entity_id=entity.id,
    )
    session.add(bill)
    session.flush()

    for li_data in line_items_data:
        if not li_data.get("account_id"):
            continue
        line = LineItem(
            narration=li_data.get("narration", ""),
            account_id=li_data["account_id"],
            amount=Decimal(str(li_data["amount"])),
            quantity=Decimal(str(li_data["quantity"])),
            tax_id=li_data.get("tax_id"),
            entity_id=entity.id,
        )
        session.add(line)
        session.flush()
        bill.line_items.add(line)
        session.flush()

    # Link bill to supplier contact
    tc = TransactionContact(
        transaction_id=bill.id,
        contact_id=po.supplier_contact_id,
    )
    session.add(tc)
    session.flush()

    return bill.id
