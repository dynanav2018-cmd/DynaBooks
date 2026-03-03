"""JSON serialization helpers for DynaBooks models."""

import json
from decimal import Decimal


def _dec(value):
    """Convert Decimal to float for JSON serialization."""
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_entity(entity):
    return {
        "id": entity.id,
        "name": entity.name,
        "year_start": entity.year_start,
        "locale": entity.locale,
        "multi_currency": entity.multi_currency,
        "currency_id": entity.currency_id,
    }


def serialize_currency(currency):
    return {
        "id": currency.id,
        "name": currency.name,
        "code": currency.code,
    }


_TYPE_GROUP_MAP = {
    "Bank": "Asset",
    "Receivable": "Asset",
    "Non Current Asset": "Asset",
    "Current Asset": "Asset",
    "Inventory": "Asset",
    "Contra Asset": "Contra Asset",
    "Payable": "Liability",
    "Control": "Liability",
    "Non Current Liability": "Liability",
    "Current Liability": "Liability",
    "Equity": "Equity",
    "Operating Revenue": "Revenue",
    "Non Operating Revenue": "Revenue",
    "Operating Expense": "Expense",
    "Direct Expense": "Expense",
    "Overhead Expense": "Expense",
    "Other Expense": "Expense",
    "Reconciliation": "Expense",
}

# Display overrides so the Category column matches the spec exactly.
_CATEGORY_DISPLAY = {
    "Direct Expense": "Operating Expense",
}


def _parse_account_number(description):
    """Extract the spec account number from a description like 'Spec #1000'."""
    if description and description.startswith("Spec #"):
        return description[6:]
    return None


def serialize_account(account):
    at_value = account.account_type.value if account.account_type else None
    acct_num = _parse_account_number(account.description)
    return {
        "id": account.id,
        "name": account.name,
        "account_code": account.account_code,
        "account_number": acct_num or account.account_code,
        "account_type": at_value,
        "type_group": _TYPE_GROUP_MAP.get(at_value, at_value),
        "category": _CATEGORY_DISPLAY.get(at_value, at_value),
        "description": account.description,
        "currency_id": account.currency_id,
    }


def serialize_tax(tax):
    return {
        "id": tax.id,
        "name": tax.name,
        "code": tax.code,
        "rate": _dec(tax.rate),
        "account_id": tax.account_id,
    }


def serialize_line_item(line_item):
    return {
        "id": line_item.id,
        "narration": line_item.narration,
        "quantity": _dec(line_item.quantity),
        "amount": _dec(line_item.amount),
        "credited": line_item.credited,
        "tax_inclusive": line_item.tax_inclusive,
        "account_id": line_item.account_id,
        "tax_id": line_item.tax_id,
    }


def serialize_transaction(transaction, session=None):
    """Serialize a transaction to a JSON-friendly dict.

    If *session* is provided, includes ``cleared_amount`` and ``outstanding``
    for clearable transactions (invoices/bills).
    """
    line_items = [serialize_line_item(li) for li in transaction.line_items]
    tax_info = None
    try:
        tax_info = {
            "total": _dec(transaction.tax.get("total", 0)),
            "taxes": {
                code: {
                    "name": info["name"],
                    "rate": _dec(info["rate"]),
                    "amount": _dec(info["amount"]),
                }
                for code, info in transaction.tax.get("taxes", {}).items()
            },
        }
    except Exception:
        pass

    result = {
        "id": transaction.id,
        "transaction_no": transaction.transaction_no,
        "transaction_date": transaction.transaction_date.isoformat()
        if transaction.transaction_date
        else None,
        "transaction_type": transaction.transaction_type.value
        if transaction.transaction_type
        else None,
        "narration": transaction.narration,
        "reference": transaction.reference,
        "amount": _dec(transaction.amount),
        "is_posted": transaction.is_posted,
        "account_id": transaction.account_id,
        "currency_id": transaction.currency_id,
        "credited": getattr(transaction, "credited", False),
        "compound": getattr(transaction, "compound", False),
        "main_account_amount": _dec(
            getattr(transaction, "main_account_amount", 0) or 0
        ),
        "line_items": line_items,
        "tax": tax_info,
    }

    # Add outstanding info for clearable transactions when session is available
    if session and transaction.is_posted and hasattr(transaction, "cleared"):
        try:
            cleared = transaction.cleared(session)
            result["cleared_amount"] = _dec(cleared)
            result["outstanding"] = _dec(transaction.amount - cleared)
        except Exception:
            pass

    return result


def serialize_assignment(assignment):
    return {
        "id": assignment.id,
        "assignment_date": assignment.assignment_date.isoformat()
        if assignment.assignment_date
        else None,
        "transaction_id": assignment.transaction_id,
        "assigned_id": assignment.assigned_id,
        "assigned_type": assignment.assigned_type,
        "assigned_no": assignment.assigned_no,
        "amount": _dec(assignment.amount),
    }


def serialize_contact(contact):
    return {
        "id": contact.id,
        "name": contact.name,
        "contact_type": contact.contact_type,
        "email": contact.email,
        "phone": contact.phone,
        "address_line_1": contact.address_line_1,
        "address_line_2": contact.address_line_2,
        "city": contact.city,
        "province_state": contact.province_state,
        "postal_code": contact.postal_code,
        "country": contact.country,
        "tax_number": contact.tax_number,
        "payment_terms_days": contact.payment_terms_days,
        "notes": contact.notes,
        "is_active": contact.is_active,
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
    }


def serialize_company_info(info):
    if not info:
        return None
    return {
        "address_line_1": info.address_line_1,
        "address_line_2": info.address_line_2,
        "city": info.city,
        "province_state": info.province_state,
        "postal_code": info.postal_code,
        "country": info.country,
        "phone": info.phone,
        "email": info.email,
        "allow_edit_posted": info.allow_edit_posted,
    }


def serialize_recurring_journal(rj):
    """Serialize a RecurringJournal template."""
    return {
        "id": rj.id,
        "name": rj.name,
        "narration": rj.narration,
        "account_id": rj.account_id,
        "line_items": json.loads(rj.line_items_json),
        "is_active": rj.is_active,
    }


def serialize_product(product):
    result = {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "default_price": _dec(product.default_price),
        "product_type": product.product_type or "product",
        "revenue_account_id": product.revenue_account_id,
        "expense_account_id": product.expense_account_id,
        "tax_id": product.tax_id,
        "is_active": product.is_active,
        "sku": getattr(product, "sku", None),
        "track_inventory": getattr(product, "track_inventory", False),
        "quantity_on_hand": _dec(getattr(product, "quantity_on_hand", 0)),
        "reorder_point": _dec(getattr(product, "reorder_point", 0)),
        "average_cost": _dec(getattr(product, "average_cost", 0)),
        "inventory_account_id": getattr(product, "inventory_account_id", None),
        "cogs_account_id": getattr(product, "cogs_account_id", None),
    }
    return result


def serialize_stock_movement(movement):
    return {
        "id": movement.id,
        "product_id": movement.product_id,
        "transaction_id": movement.transaction_id,
        "purchase_order_id": movement.purchase_order_id,
        "movement_type": movement.movement_type,
        "quantity_change": _dec(movement.quantity_change),
        "unit_cost": _dec(movement.unit_cost),
        "total_cost": _dec(movement.total_cost),
        "quantity_after": _dec(movement.quantity_after),
        "average_cost_after": _dec(movement.average_cost_after),
        "reference": movement.reference,
        "notes": movement.notes,
        "created_at": movement.created_at.isoformat() if movement.created_at else None,
    }


def serialize_purchase_order(po, lines=None):
    result = {
        "id": po.id,
        "po_number": po.po_number,
        "supplier_contact_id": po.supplier_contact_id,
        "order_date": po.order_date.isoformat() if po.order_date else None,
        "expected_date": po.expected_date.isoformat() if po.expected_date else None,
        "status": po.status,
        "notes": po.notes,
        "created_at": po.created_at.isoformat() if po.created_at else None,
        "updated_at": po.updated_at.isoformat() if po.updated_at else None,
    }
    if lines is not None:
        result["lines"] = [serialize_purchase_order_line(l) for l in lines]
        result["total"] = sum(
            _dec(l.quantity_ordered) * _dec(l.unit_cost) for l in lines
        )
    return result


def serialize_purchase_order_line(line):
    return {
        "id": line.id,
        "purchase_order_id": line.purchase_order_id,
        "product_id": line.product_id,
        "description": line.description,
        "quantity_ordered": _dec(line.quantity_ordered),
        "quantity_received": _dec(line.quantity_received),
        "unit_cost": _dec(line.unit_cost),
        "tax_id": line.tax_id,
    }


def _serialize_value(value):
    """Recursively serialize report data, converting Decimals and Account objects."""
    from python_accounting.models import Account

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Account):
        return serialize_account(value)
    if isinstance(value, dict):
        return {
            (k.value if hasattr(k, "value") else str(k)): _serialize_value(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, set)):
        return [_serialize_value(item) for item in value]
    if isinstance(value, (int, float, bool, str, type(None))):
        return value
    # Fallback for enums or other objects with .value
    if hasattr(value, "value"):
        return value.value
    return str(value)


def serialize_report_section(balances, accounts, totals, result_amounts):
    """Serialize a financial report's data structures into JSON-friendly dicts."""
    return {
        "balances": _serialize_value(balances or {}),
        "totals": _serialize_value(totals or {}),
        "result_amounts": _serialize_value(result_amounts or {}),
        "accounts": _serialize_value(accounts or {}),
    }
