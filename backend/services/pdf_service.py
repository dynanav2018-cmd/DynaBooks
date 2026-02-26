"""PDF rendering service using xhtml2pdf."""

import io
import os

from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

_template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_jinja_env = Environment(loader=FileSystemLoader(_template_dir), autoescape=True)


def render_invoice_pdf(invoice_data, company_data, contact=None):
    """Render an invoice as a PDF. Returns bytes."""
    template = _jinja_env.get_template("invoice_pdf.html")
    html = template.render(
        invoice=invoice_data,
        company=company_data,
        contact=contact,
    )
    return _html_to_pdf(html)


def render_report_pdf(report_title, report_data, company_data, date_range=""):
    """Render a financial report as a PDF. Returns bytes."""
    template = _jinja_env.get_template("report_pdf.html")
    html = template.render(
        report_title=report_title,
        balances=report_data.get("balances", {}),
        totals=report_data.get("totals", {}),
        result_amounts=report_data.get("result_amounts", {}),
        company=company_data,
        date_range=date_range,
    )
    return _html_to_pdf(html)


def _html_to_pdf(html_string):
    """Convert an HTML string to PDF bytes using xhtml2pdf."""
    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=buffer)
    if pisa_status.err:
        raise RuntimeError(f"PDF generation failed with {pisa_status.err} errors")
    return buffer.getvalue()
