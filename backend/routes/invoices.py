"""Client Invoice routes."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, g, jsonify, request
from sqlalchemy import text

from python_accounting.models import Account, LineItem, Tax, Transaction
from python_accounting.transactions import ClientInvoice

from backend.models.company_info import CompanyInfo
from backend.models.contact import Contact, TransactionAddress
from backend.models.transaction_contact import TransactionContact
from backend.serializers import serialize_transaction
from backend.services.inventory import (
    check_stock_availability,
    create_cogs_journal_entry,
    get_inventory_products_from_line_items,
    record_stock_sale,
    reverse_cogs_journal,
    reverse_stock_movements,
)

bp = Blueprint("invoices", __name__, url_prefix="/api")


def _check_and_unpost(session, transaction, transaction_id):
    """If posted and allow_edit_posted is on, un-post via raw SQL.

    Also reverses any inventory stock movements and COGS journals that
    were auto-created when the invoice was posted.
    """
    if not transaction.is_posted:
        return None
    info = session.query(CompanyInfo).filter(
        CompanyInfo.entity_id == session.entity.id
    ).first()
    if not info or not info.allow_edit_posted:
        return jsonify(error="Cannot modify a posted invoice"), 400
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
    reverse_cogs_journal(session, transaction_id)
    reverse_stock_movements(session, transaction_id)

    session.expire(transaction)
    return None


def _get_invoices(session):
    return (
        session.query(ClientInvoice)
        .filter(Transaction.transaction_type == Transaction.TransactionType.CLIENT_INVOICE)
        .all()
    )


def _serialize_with_contact(invoice, session=None):
    """Serialize invoice and include contact_id from TransactionContact."""
    data = serialize_transaction(invoice, session=session)
    tc = (
        g.session.query(TransactionContact)
        .filter(TransactionContact.transaction_id == invoice.id)
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
        .filter(TransactionAddress.transaction_id == invoice.id)
        .first()
    )
    data["billing_address_id"] = ta.billing_address_id if ta else None
    data["shipping_address_id"] = ta.shipping_address_id if ta else None
    return data


@bp.route("/invoices", methods=["GET"])
def list_invoices():
    invoices = _get_invoices(g.session)
    return jsonify([_serialize_with_contact(inv, session=g.session) for inv in invoices])


@bp.route("/invoices/<int:invoice_id>", methods=["GET"])
def get_invoice(invoice_id):
    invoice = g.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return jsonify(error="Invoice not found"), 404
    return jsonify(_serialize_with_contact(invoice))


@bp.route("/invoices", methods=["POST"])
def create_invoice():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    narration = data.get("narration", "Client Invoice")
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

    # Default to first RECEIVABLE account
    if not account_id:
        receivable = g.session.query(Account).filter(
            Account.account_type == Account.AccountType.RECEIVABLE
        ).first()
        if not receivable:
            return jsonify(error="No receivable account found"), 400
        account_id = receivable.id

    try:
        invoice = ClientInvoice(
            narration=narration,
            transaction_date=tx_date,
            account_id=account_id,
            entity_id=entity.id,
        )
        g.session.add(invoice)
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
            invoice.line_items.add(line)
            g.session.flush()

        # Link contact if provided
        contact_id = data.get("contact_id")
        if contact_id:
            tc = TransactionContact(
                transaction_id=invoice.id, contact_id=contact_id
            )
            g.session.add(tc)

        # Save address selections
        billing_addr_id = data.get("billing_address_id")
        shipping_addr_id = data.get("shipping_address_id")
        if billing_addr_id or shipping_addr_id:
            ta = TransactionAddress(
                transaction_id=invoice.id,
                billing_address_id=billing_addr_id,
                shipping_address_id=shipping_addr_id,
            )
            g.session.add(ta)

        # Auto-post if requested
        if data.get("post", False):
            inv_items = get_inventory_products_from_line_items(
                g.session, list(invoice.line_items)
            )
            if inv_items:
                errors = check_stock_availability(g.session, inv_items)
                if errors:
                    g.session.rollback()
                    return jsonify(error="; ".join(errors)), 400

            invoice.post(g.session)

            if inv_items:
                for li, product in inv_items:
                    record_stock_sale(
                        g.session,
                        product,
                        Decimal(str(li.quantity)),
                        transaction_id=invoice.id,
                        reference=invoice.transaction_no or "",
                    )
                create_cogs_journal_entry(g.session, invoice, inv_items)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(invoice)), 201


@bp.route("/invoices/<int:invoice_id>", methods=["PUT"])
def update_invoice(invoice_id):
    invoice = g.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return jsonify(error="Invoice not found"), 404

    err = _check_and_unpost(g.session, invoice, invoice_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    # Loaded objects lack __init__-set attributes needed by
    # python-accounting's before_flush validator. Set them now
    # before any changes that would mark the object dirty.
    if not hasattr(invoice, 'main_account_types'):
        invoice.main_account_types = [Account.AccountType.RECEIVABLE]
        invoice.credited = False
        invoice.line_item_types = [Account.AccountType.OPERATING_REVENUE]
        invoice.account_type_map = {
            "ClientInvoice": Account.AccountType.RECEIVABLE,
        }

    # Update basic fields
    if "narration" in data:
        invoice.narration = data["narration"]
    if "reference" in data:
        invoice.reference = data["reference"]
    if "transaction_date" in data:
        try:
            invoice.transaction_date = datetime.fromisoformat(data["transaction_date"])
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
                {"tid": invoice_id},
            )
            g.session.flush()

            # Expire to clear stale line_items relationship, then
            # re-set init attrs the library needs for validation.
            g.session.expire(invoice)
            invoice.main_account_types = [Account.AccountType.RECEIVABLE]
            invoice.credited = False
            invoice.line_item_types = [Account.AccountType.OPERATING_REVENUE]
            invoice.account_type_map = {
                "ClientInvoice": Account.AccountType.RECEIVABLE,
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
                invoice.line_items.add(line)
                g.session.flush()

            invoice.main_account_amount = invoice.amount

        # Update contact link if contact_id provided
        contact_id = data.get("contact_id")
        if contact_id is not None:
            # Remove existing link via raw SQL
            conn = g.session.connection()
            conn.execute(
                text('DELETE FROM transaction_contacts WHERE transaction_id = :tid'),
                {"tid": invoice_id},
            )
            if contact_id:
                tc = TransactionContact(
                    transaction_id=invoice.id, contact_id=contact_id
                )
                g.session.add(tc)

        # Update address selections
        if "billing_address_id" in data or "shipping_address_id" in data:
            conn2 = g.session.connection()
            conn2.execute(
                text("DELETE FROM transaction_addresses WHERE transaction_id = :tid"),
                {"tid": invoice_id},
            )
            billing_addr_id = data.get("billing_address_id")
            shipping_addr_id = data.get("shipping_address_id")
            if billing_addr_id or shipping_addr_id:
                ta = TransactionAddress(
                    transaction_id=invoice.id,
                    billing_address_id=billing_addr_id,
                    shipping_address_id=shipping_addr_id,
                )
                g.session.add(ta)

        # Auto-post if requested
        if data.get("post", False):
            inv_items = get_inventory_products_from_line_items(
                g.session, list(invoice.line_items)
            )
            if inv_items:
                errors = check_stock_availability(g.session, inv_items)
                if errors:
                    g.session.rollback()
                    return jsonify(error="; ".join(errors)), 400

            invoice.post(g.session)

            if inv_items:
                for li, product in inv_items:
                    record_stock_sale(
                        g.session,
                        product,
                        Decimal(str(li.quantity)),
                        transaction_id=invoice.id,
                        reference=invoice.transaction_no or "",
                    )
                create_cogs_journal_entry(g.session, invoice, inv_items)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(_serialize_with_contact(invoice))


@bp.route("/invoices/<int:invoice_id>", methods=["DELETE"])
def delete_invoice(invoice_id):
    invoice = g.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return jsonify(error="Invoice not found"), 404

    err = _check_and_unpost(g.session, invoice, invoice_id)
    if err:
        return err

    try:
        g.session.delete(invoice)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Invoice deleted"), 200


@bp.route("/invoices/<int:invoice_id>/post", methods=["POST"])
def post_invoice(invoice_id):
    invoice = g.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return jsonify(error="Invoice not found"), 404

    if invoice.is_posted:
        return jsonify(error="Invoice is already posted"), 409

    try:
        # Check stock availability for inventory products
        inv_items = get_inventory_products_from_line_items(
            g.session, list(invoice.line_items)
        )
        if inv_items:
            errors = check_stock_availability(g.session, inv_items)
            if errors:
                return jsonify(error="; ".join(errors)), 400

        invoice.post(g.session)

        # Record stock sales and auto-create COGS journal
        if inv_items:
            for li, product in inv_items:
                record_stock_sale(
                    g.session,
                    product,
                    Decimal(str(li.quantity)),
                    transaction_id=invoice.id,
                    reference=invoice.transaction_no or "",
                )
            create_cogs_journal_entry(g.session, invoice, inv_items)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_transaction(invoice))
