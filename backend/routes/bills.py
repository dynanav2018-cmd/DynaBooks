"""Supplier Bill routes."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request
from sqlalchemy import text

from python_accounting.models import Account, LineItem, Transaction
from python_accounting.transactions import SupplierBill

from backend.models.company_info import CompanyInfo
from backend.models.contact import Contact, TransactionAddress
from backend.models.transaction_contact import TransactionContact
from backend.serializers import serialize_transaction

bp = Blueprint("bills", __name__, url_prefix="/api")


def _check_and_unpost(session, transaction, transaction_id):
    """If posted and allow_edit_posted is on, un-post via raw SQL."""
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
        g.session.flush()

        for li_data in line_items_data:
            line = LineItem(
                narration=li_data.get("narration", ""),
                account_id=li_data["account_id"],
                amount=Decimal(str(li_data["amount"])),
                quantity=Decimal(str(li_data.get("quantity", 1))),
                tax_id=li_data.get("tax_id"),
                entity_id=entity.id,
            )
            g.session.add(line)
            g.session.flush()
            bill.line_items.add(line)
            g.session.flush()

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
            bill.post(g.session)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(bill)), 201


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
            for li_data in line_items_data:
                line = LineItem(
                    narration=li_data.get("narration", ""),
                    account_id=li_data["account_id"],
                    amount=Decimal(str(li_data["amount"])),
                    quantity=Decimal(str(li_data.get("quantity", 1))),
                    tax_id=li_data.get("tax_id"),
                    entity_id=entity.id,
                )
                g.session.add(line)
                g.session.flush()
                bill.line_items.add(line)
                g.session.flush()

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
            bill.post(g.session)

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
        bill.post(g.session)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(bill))
