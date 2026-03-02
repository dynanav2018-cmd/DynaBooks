"""PDF generation routes."""

from datetime import datetime

from flask import Blueprint, Response, g, jsonify, request

from python_accounting.models import Account
from python_accounting.reports import (
    IncomeStatement,
    BalanceSheet,
    AgingSchedule,
)
from python_accounting.transactions import ClientInvoice, SupplierBill

from backend.models.contact import Contact
from backend.models.company_info import CompanyInfo
from backend.models.transaction_contact import TransactionContact
from backend.serializers import (
    serialize_transaction,
    serialize_entity,
    serialize_contact,
    serialize_company_info,
    serialize_report_section,
    _dec,
)
from backend.services.pdf_service import render_invoice_pdf, render_report_pdf

bp = Blueprint("pdf", __name__, url_prefix="/api")


def _get_company_info_data():
    """Load company info for PDF templates."""
    info = g.session.query(CompanyInfo).filter(
        CompanyInfo.entity_id == g.session.entity.id
    ).first()
    return serialize_company_info(info)


@bp.route("/invoices/<int:invoice_id>/pdf", methods=["GET"])
def invoice_pdf(invoice_id):
    invoice = g.session.get(ClientInvoice, invoice_id)
    if not invoice:
        return jsonify(error="Invoice not found"), 404

    invoice_data = serialize_transaction(invoice)
    company_data = serialize_entity(g.session.entity)
    company_info = _get_company_info_data()

    # Look up linked contact
    contact_data = None
    tc = (
        g.session.query(TransactionContact)
        .filter(TransactionContact.transaction_id == invoice_id)
        .first()
    )
    if tc:
        contact = g.session.get(Contact, tc.contact_id)
        if contact:
            contact_data = serialize_contact(contact)

    pdf_bytes = render_invoice_pdf(invoice_data, company_data, contact_data, company_info)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=invoice-{invoice_data.get('transaction_no', invoice_id)}.pdf"
        },
    )


@bp.route("/bills/<int:bill_id>/pdf", methods=["GET"])
def bill_pdf(bill_id):
    bill = g.session.get(SupplierBill, bill_id)
    if not bill:
        return jsonify(error="Bill not found"), 404

    bill_data = serialize_transaction(bill)
    company_data = serialize_entity(g.session.entity)
    company_info = _get_company_info_data()

    # Look up linked contact
    contact_data = None
    tc = (
        g.session.query(TransactionContact)
        .filter(TransactionContact.transaction_id == bill_id)
        .first()
    )
    if tc:
        contact = g.session.get(Contact, tc.contact_id)
        if contact:
            contact_data = serialize_contact(contact)

    pdf_bytes = render_invoice_pdf(bill_data, company_data, contact_data, company_info)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=bill-{bill_data.get('transaction_no', bill_id)}.pdf"
        },
    )


def _parse_date(param_name):
    value = request.args.get(param_name)
    if not value:
        return None, None
    try:
        return datetime.fromisoformat(value), None
    except ValueError:
        return None, (jsonify(error=f"Invalid {param_name} format"), 400)


def _build_account_listing(session, report):
    """Build a complete account listing grouped by type, with balances.

    Returns a dict like::

        {"Operating Expense": [{"name": "Rent", "balance": 500.0}, ...], ...}

    Every account in the Chart of Accounts is included, even if the
    balance is zero, so the PDF shows all line items.
    """
    entity_id = session.entity.id
    all_accounts = (
        session.query(Account)
        .filter(Account.entity_id == entity_id)
        .order_by(Account.account_code)
        .all()
    )

    # Build a lookup: account_type_value -> {account_id: balance}
    balance_lookup: dict[str, dict[int, float]] = {}
    if hasattr(report, "balances") and report.balances:
        for acct_type, type_balances in report.balances.items():
            type_str = acct_type.value if hasattr(acct_type, "value") else str(acct_type)
            balance_lookup[type_str] = {}
            if isinstance(type_balances, dict):
                for acct_obj, amt in type_balances.items():
                    if hasattr(acct_obj, "id"):
                        balance_lookup[type_str][acct_obj.id] = float(amt)

    listing: dict[str, list[dict]] = {}
    for acct in all_accounts:
        type_str = acct.account_type.value if acct.account_type else None
        if not type_str:
            continue
        if type_str not in listing:
            listing[type_str] = []
        balance = balance_lookup.get(type_str, {}).get(acct.id, 0.0)
        listing[type_str].append({"name": acct.name, "balance": balance})

    return listing


REPORT_TITLES = {
    "income-statement": "Profit & Loss Statement",
    "balance-sheet": "Balance Sheet",
    "aging-receivables": "Aging Schedule - Receivables",
    "aging-payables": "Aging Schedule - Payables",
}


@bp.route("/reports/<report_type>/pdf", methods=["GET"])
def report_pdf(report_type):
    if report_type not in REPORT_TITLES:
        return jsonify(error=f"Unknown report type: {report_type}"), 400

    company_data = serialize_entity(g.session.entity)
    title = REPORT_TITLES[report_type]
    date_range = ""

    try:
        if report_type == "income-statement":
            start_date, err = _parse_date("from")
            if err:
                return err
            end_date, err = _parse_date("to")
            if err:
                return err
            report = IncomeStatement(g.session, start_date, end_date)
            report_data = serialize_report_section(
                report.balances, report.accounts, report.totals, report.result_amounts
            )
            report_data["account_listing"] = _build_account_listing(
                g.session, report
            )
            if start_date and end_date:
                date_range = f"{start_date.strftime('%B %Y')}-{end_date.strftime('%B %Y')}"

        elif report_type == "balance-sheet":
            as_of, err = _parse_date("as_of")
            if err:
                return err
            report = BalanceSheet(g.session, as_of)
            report_data = serialize_report_section(
                report.balances, report.accounts, report.totals, report.result_amounts
            )
            report_data["account_listing"] = _build_account_listing(
                g.session, report
            )
            if as_of:
                date_range = f"As of {as_of.strftime('%B %d, %Y')}"

        elif report_type in ("aging-receivables", "aging-payables"):
            as_of, err = _parse_date("as_of")
            if err:
                return err
            acct_type = (
                Account.AccountType.RECEIVABLE
                if report_type == "aging-receivables"
                else Account.AccountType.PAYABLE
            )
            report = AgingSchedule(g.session, acct_type, as_of)
            report_data = {
                "balances": {k: _dec(v) for k, v in report.balances.items()},
                "result_amounts": {},
            }
            # Fetch per-contact detail for aging reports
            from backend.routes.reports import _build_aging_detail
            aging_detail = _build_aging_detail(g.session, acct_type, as_of)
            report_data["aging_detail"] = aging_detail
            if as_of:
                date_range = f"As of {as_of.strftime('%b %d, %Y')}"

    except Exception as e:
        return jsonify(error=str(e)), 400

    company_info = _get_company_info_data()
    pdf_bytes = render_report_pdf(
        title, report_data, company_data, date_range,
        company_info=company_info, report_type=report_type,
    )
    filename = f"{report_type}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )
