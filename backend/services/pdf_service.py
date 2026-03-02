"""PDF rendering service using xhtml2pdf."""

import base64
import io
import os

from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

import sys

if getattr(sys, 'frozen', False):
    _template_dir = os.path.join(sys._MEIPASS, "backend", "templates")
else:
    _template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_jinja_env = Environment(loader=FileSystemLoader(_template_dir), autoescape=True)


def _load_logo_base64():
    """Load the company logo as a base64 data URI, or return None.

    Checks for a per-company logo first (via Flask request context),
    falls back to the default logo location.
    """
    from backend.data_dir import get_logo_path, get_company_logo_path

    logo_path = None
    try:
        from flask import request as _req
        company_slug = _req.headers.get("X-Company")
        if company_slug:
            logo_path = get_company_logo_path(company_slug)
    except RuntimeError:
        pass  # Outside request context

    if not logo_path or not os.path.isfile(logo_path):
        logo_path = get_logo_path()

    if not os.path.isfile(logo_path):
        return None
    with open(logo_path, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_invoice_pdf(invoice_data, company_data, contact=None, company_info=None):
    """Render an invoice as a PDF. Returns bytes."""
    template = _jinja_env.get_template("invoice_pdf.html")
    html = template.render(
        invoice=invoice_data,
        company=company_data,
        contact=contact,
        company_info=company_info,
        logo_base64=_load_logo_base64(),
    )
    return _html_to_pdf(html)


def render_report_pdf(
    report_title, report_data, company_data, date_range="",
    company_info=None, report_type="",
):
    """Render a financial report as a PDF. Returns bytes."""
    from datetime import datetime

    template = _jinja_env.get_template("report_pdf.html")
    html = template.render(
        report_title=report_title,
        report_type=report_type,
        balances=report_data.get("balances", {}),
        accounts=report_data.get("accounts", {}),
        totals=report_data.get("totals", {}),
        result_amounts=report_data.get("result_amounts", {}),
        account_listing=report_data.get("account_listing", {}),
        aging_detail=report_data.get("aging_detail"),
        company=company_data,
        company_info=company_info,
        date_range=date_range,
        print_date=datetime.now().strftime("%m-%d-%y"),
        print_time=datetime.now().strftime("%I:%M:%S %p").lstrip("0"),
        logo_base64=_load_logo_base64(),
    )
    return _html_to_pdf(html)


def _html_to_pdf(html_string):
    """Convert an HTML string to PDF bytes using xhtml2pdf."""
    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=buffer)
    if pisa_status.err:
        raise RuntimeError(f"PDF generation failed with {pisa_status.err} errors")
    return buffer.getvalue()
