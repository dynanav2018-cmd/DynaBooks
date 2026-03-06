"""Supplier Bill routes."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request
from sqlalchemy import text

from python_accounting.models import Account, LineItem, Tax, Transaction
from python_accounting.transactions import SupplierBill

from backend.models.company_info import CompanyInfo
from backend.models.contact import Contact, TransactionAddress
from backend.models.transaction_contact import TransactionContact
from backend.serializers import serialize_transaction
from backend.services.inventory import (
    get_inventory_products_from_line_items,
    record_stock_purchase,
    reverse_stock_movements,
)

bp = Blueprint("bills", __name__, url_prefix="/api")


def _post_bill_with_inventory(session, bill, inv_items):
    """Post a bill and handle inventory effects atomically.

    The library's post() calls session.commit() internally, so if the
    subsequent stock operations fail we must manually un-post.
    """
    bill.post(session)
    # At this point the bill post is committed to the DB.

    if not inv_items:
        return

    try:
        for li, product in inv_items:
            unit_cost = Decimal(str(li.amount))
            record_stock_purchase(
                session,
                product,
                Decimal(str(li.quantity)),
                unit_cost,
                transaction_id=bill.id,
                reference=bill.transaction_no or "",
            )
        session.commit()
    except Exception:
        session.rollback()
        _force_unpost_bill(session, bill.id)
        session.commit()
        raise


def _force_unpost_bill(session, transaction_id):
    """Remove ledger entries for a transaction via raw SQL."""
    conn = session.connection()
    ledger_ids = [
        r[0]
        for r in conn.execute(
            text("SELECT id FROM ledger WHERE transaction_id = :tid"),
            {"tid": transaction_id},
        )
    ]
    if ledger_ids:
        conn.execute(
            text("DELETE FROM ledger WHERE transaction_id = :tid"),
            {"tid": transaction_id},
        )
        for lid in ledger_ids:
            conn.execute(text("DELETE FROM recyclable WHERE id = :id"), {"id": lid})


def _create_line_items(session, transaction, line_items_data, entity_id):
    """Create line items for a transaction, including hidden tax2 lines."""
    for i, li_data in enumerate(line_items_data):
        line = LineItem(
            narration=li_data.get("narration", ""),
            account_id=li_data["account_id"],
            amount=Decimal(str(li_data["amount"])),
            quantity=Decimal(str(li_data.get("quantity", 1))),
            tax_id=li_data.get("tax_id"),
            entity_id=entity_id,
        )
        session.add(line)
        session.flush()
        transaction.line_items.add(line)
        session.flush()

        # Create hidden line for secondary tax
        tax_id_2 = li_data.get("tax_id_2")
        if tax_id_2:
            tax2 = session.get(Tax, tax_id_2)
            if tax2:
                line_amount = Decimal(str(li_data["amount"])) * Decimal(str(li_data.get("quantity", 1)))
                tax2_amount = (line_amount * tax2.rate / Decimal("100")).quantize(Decimal("0.01"))

                # Add the tax2 account's type to allowed line_item_types
                tax2_account = session.get(Account, tax2.account_id)
                if tax2_account and tax2_account.account_type not in transaction.line_item_types:
                    transaction.line_item_types = list(transaction.line_item_types) + [tax2_account.account_type]

                hidden = LineItem(
                    narration=f"[TAX2:{tax2.id}:L{i}]",
                    account_id=tax2.account_id,
                    amount=tax2_amount,
                    quantity=Decimal("1"),
                    tax_id=None,
                    entity_id=entity_id,
                )
                session.add(hidden)
                session.flush()
                transaction.line_items.add(hidden)
                session.flush()


def _check_and_unpost(session, transaction, transaction_id):
    """If posted and allow_edit_posted is on, un-post via raw SQL.

    Also reverses any inventory stock movements that were auto-created
    when the bill was posted.
    """
    if not transaction.is_posted:
        return None
    info = session.query(CompanyInfo).filter(
        CompanyInfo.entity_id == session.entity.id
    ).first()
    if not info or not info.allow_edit_posted:
        return jsonify(error="Cannot modify a posted bill"), 400
    conn = session.connection()
    ledger_ids = [r[0] for r in conn.execute(
        text("SELECT id FROM ledger WHERE transaction_id = :tid"),
        {"tid": transaction_id},
    )]
    if ledger_ids:
        conn.execute(
            text("DELETE FROM ledger WHERE transaction_id = :tid"),
            {"tid": transaction_id},
        )
        for lid in ledger_ids:
            conn.execute(text("DELETE FROM recyclable WHERE id = :id"), {"id": lid})

    # Reverse inventory effects
    reverse_stock_movements(session, transaction_id)

    session.expire(transaction)
    return None


def _get_bills(session):
    return (
        session.query(SupplierBill)
        .filter(Transaction.transaction_type == Transaction.TransactionType.SUPPLIER_BILL)
        .all()
    )


def _serialize_with_contact(bill, session=None):
    """Serialize bill and include contact_id from TransactionContact."""
    data = serialize_transaction(bill, session=session)
    tc = (
        g.session.query(TransactionContact)
        .filter(TransactionContact.transaction_id == bill.id)
        .first()
    )
    data["contact_id"] = tc.contact_id if tc else None
    if tc:
        contact = g.session.get(Contact, tc.contact_id)
        data["contact_name"] = contact.name if contact else None
    else:
        data["contact_name"] = None
    # Include address selections
    ta = (
        g.session.query(TransactionAddress)
        .filter(TransactionAddress.transaction_id == bill.id)
        .first()
    )
    data["billing_address_id"] = ta.billing_address_id if ta else None
    data["shipping_address_id"] = ta.shipping_address_id if ta else None
    return data


@bp.route("/bills", methods=["GET"])
def list_bills():
    bills = _get_bills(g.session)
    return jsonify([_serialize_with_contact(b, session=g.session) for b in bills])


@bp.route("/bills/<int:bill_id>", methods=["GET"])
def get_bill(bill_id):
    bill = g.session.get(SupplierBill, bill_id)
    if not bill:
        return jsonify(error="Bill not found"), 404
    return jsonify(_serialize_with_contact(bill))


@bp.route("/bills", methods=["POST"])
def create_bill():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    narration = data.get("narration", "Supplier Bill")
    transaction_date = data.get("transaction_date")
    account_id = data.get("account_id")
    line_items_data = data.get("line_items", [])

    if not transaction_date:
        return jsonify(error="transaction_date is required"), 400
    if not line_items_data:
        return jsonify(error="At least one line_item is required"), 400

    try:
        tx_date = datetime.fromisoformat(transaction_date)
    except ValueError:
        return jsonify(error="Invalid transaction_date format"), 400

    entity = g.session.entity

    # Default to first PAYABLE account
    if not account_id:
        payable = g.session.query(Account).filter(
            Account.account_type == Account.AccountType.PAYABLE
        ).first()
        if not payable:
            return jsonify(error="No payable account found"), 400
        account_id = payable.id

    try:
        bill = SupplierBill(
            narration=narration,
            transaction_date=tx_date,
            account_id=account_id,
            entity_id=entity.id,
        )
        g.session.add(bill)
        if data.get("reference"):
            bill.reference = data["reference"]
        g.session.flush()

        _create_line_items(g.session, bill, line_items_data, entity.id)

        contact_id = data.get("contact_id")
        if contact_id:
            tc = TransactionContact(
                transaction_id=bill.id, contact_id=contact_id
            )
            g.session.add(tc)

        # Save address selections
        billing_addr_id = data.get("billing_address_id")
        shipping_addr_id = data.get("shipping_address_id")
        if billing_addr_id or shipping_addr_id:
            ta = TransactionAddress(
                transaction_id=bill.id,
                billing_address_id=billing_addr_id,
                shipping_address_id=shipping_addr_id,
            )
            g.session.add(ta)

        if data.get("post", False):
            inv_items = get_inventory_products_from_line_items(
                g.session, list(bill.line_items)
            )
            _post_bill_with_inventory(g.session, bill, inv_items)
        else:
            g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(bill, session=g.session)), 201


@bp.route("/bills/<int:bill_id>", methods=["PUT"])
def update_bill(bill_id):
    bill = g.session.get(SupplierBill, bill_id)
    if not bill:
        return jsonify(error="Bill not found"), 404

    err = _check_and_unpost(g.session, bill, bill_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    # Loaded objects lack __init__-set attributes needed by
    # python-accounting's before_flush validator. Set them now
    # before any changes that would mark the object dirty.
    if not hasattr(bill, 'main_account_types'):
        bill.main_account_types = [Account.AccountType.PAYABLE]
        bill.credited = True
        bill.line_item_types = Account.purchasables
        bill.account_type_map = {
            "SupplierBill": Account.AccountType.PAYABLE,
        }

    # Update basic fields
    if "narration" in data:
        bill.narration = data["narration"]
    if "reference" in data:
        bill.reference = data["reference"]
    if "transaction_date" in data:
        try:
            bill.transaction_date = datetime.fromisoformat(data["transaction_date"])
        except ValueError:
            return jsonify(error="Invalid transaction_date format"), 400

    try:
        # Replace line items if provided
        line_items_data = data.get("line_items")
        if line_items_data is not None:
            # Delete existing line items via raw SQL
            # (AccountingSession doesn't support ORM Delete objects)
            conn = g.session.connection()
            conn.execute(
                text('DELETE FROM line_item WHERE transaction_id = :tid'),
                {"tid": bill_id},
            )
            g.session.flush()

            # Expire to clear stale line_items relationship, then
            # re-set init attrs the library needs for validation.
            g.session.expire(bill)
            bill.main_account_types = [Account.AccountType.PAYABLE]
            bill.credited = True
            bill.line_item_types = Account.purchasables
            bill.account_type_map = {
                "SupplierBill": Account.AccountType.PAYABLE,
            }

            entity = g.session.entity

            # Recreate line items using .line_items.add() so the
            # library's @validates flips credited correctly.
            _create_line_items(g.session, bill, line_items_data, entity.id)

            bill.main_account_amount = bill.amount

        # Update contact link if contact_id provided
        contact_id = data.get("contact_id")
        if contact_id is not None:
            conn = g.session.connection()
            conn.execute(
                text('DELETE FROM transaction_contacts WHERE transaction_id = :tid'),
                {"tid": bill_id},
            )
            if contact_id:
                tc = TransactionContact(
                    transaction_id=bill.id, contact_id=contact_id
                )
                g.session.add(tc)

        # Update address selections
        if "billing_address_id" in data or "shipping_address_id" in data:
            conn3 = g.session.connection()
            conn3.execute(
                text("DELETE FROM transaction_addresses WHERE transaction_id = :tid"),
                {"tid": bill_id},
            )
            billing_addr_id = data.get("billing_address_id")
            shipping_addr_id = data.get("shipping_address_id")
            if billing_addr_id or shipping_addr_id:
                ta = TransactionAddress(
                    transaction_id=bill.id,
                    billing_address_id=billing_addr_id,
                    shipping_address_id=shipping_addr_id,
                )
                g.session.add(ta)

        # Auto-post if requested
        if data.get("post", False):
            inv_items = get_inventory_products_from_line_items(
                g.session, list(bill.line_items)
            )
            _post_bill_with_inventory(g.session, bill, inv_items)
        else:
            g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(_serialize_with_contact(bill))


@bp.route("/bills/<int:bill_id>", methods=["DELETE"])
def delete_bill(bill_id):
    bill = g.session.get(SupplierBill, bill_id)
    if not bill:
        return jsonify(error="Bill not found"), 404

    # Set runtime attrs the library's before_flush validator expects
    if not hasattr(bill, 'main_account_types'):
        bill.main_account_types = [Account.AccountType.PAYABLE]
        bill.credited = True
        bill.line_item_types = Account.purchasables
        bill.account_type_map = {
            "SupplierBill": Account.AccountType.PAYABLE,
        }

    err = _check_and_unpost(g.session, bill, bill_id)
    if err:
        return err

    try:
        g.session.delete(bill)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Bill deleted"), 200


@bp.route("/bills/<int:bill_id>/post", methods=["POST"])
def post_bill(bill_id):
    bill = g.session.get(SupplierBill, bill_id)
    if not bill:
        return jsonify(error="Bill not found"), 404

    if bill.is_posted:
        return jsonify(error="Bill is already posted"), 409

    try:
        inv_items = get_inventory_products_from_line_items(
            g.session, list(bill.line_items)
        )
        _post_bill_with_inventory(g.session, bill, inv_items)
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(bill, session=g.session))
