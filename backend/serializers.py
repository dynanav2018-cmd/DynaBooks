"""JSON serialization helpers for DynaBooks models."""

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


def serialize_account(account):
    return {
        "id": account.id,
        "name": account.name,
        "account_code": account.account_code,
        "account_type": account.account_type.value if account.account_type else None,
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


def serialize_transaction(transaction):
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

    return {
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
        "line_items": line_items,
        "tax": tax_info,
    }


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
        "country": contact.country,
        "tax_number": contact.tax_number,
        "payment_terms_days": contact.payment_terms_days,
        "notes": contact.notes,
        "is_active": contact.is_active,
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
    }


def serialize_product(product):
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "default_price": _dec(product.default_price),
        "revenue_account_id": product.revenue_account_id,
        "tax_id": product.tax_id,
        "is_active": product.is_active,
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
