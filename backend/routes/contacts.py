"""Client & Supplier contacts routes."""

import csv
import io
import json

from flask import Blueprint, g, jsonify, request

from backend.models.contact import Contact, ContactAddress
from backend.serializers import serialize_contact, serialize_contact_address

bp = Blueprint("contacts", __name__, url_prefix="/api")


def _get_addresses(session, contact_id):
    """Return all addresses for a contact."""
    return (
        session.query(ContactAddress)
        .filter(ContactAddress.contact_id == contact_id)
        .all()
    )


@bp.route("/contacts", methods=["GET"])
def list_contacts():
    query = g.session.query(Contact)

    contact_type = request.args.get("type")
    if contact_type and contact_type in ("client", "supplier"):
        # "both" contacts should also appear in client or supplier filters
        query = query.filter(
            (Contact.contact_type == contact_type) | (Contact.contact_type == "both")
        )

    show_inactive = request.args.get("include_inactive")
    if not show_inactive:
        query = query.filter(Contact.is_active == True)

    contacts = query.all()
    result = []
    for c in contacts:
        addrs = _get_addresses(g.session, c.id)
        result.append(serialize_contact(c, addresses=addrs))
    return jsonify(result)


@bp.route("/contacts", methods=["POST"])
def create_contact():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    name = data.get("name")
    contact_type = data.get("contact_type")

    if not name or not contact_type:
        return jsonify(error="name and contact_type are required"), 400

    if contact_type not in ("client", "supplier", "both"):
        return jsonify(error="contact_type must be client, supplier, or both"), 400

    contact = Contact(
        name=name,
        contact_type=contact_type,
        company=data.get("company"),
        website=data.get("website"),
        email=data.get("email"),
        phone_1=data.get("phone_1"),
        phone_1_label=data.get("phone_1_label"),
        phone_2=data.get("phone_2"),
        phone_2_label=data.get("phone_2_label"),
        tax_number=data.get("tax_number"),
        payment_terms=data.get("payment_terms", "30 Days"),
        default_tax_id=data.get("default_tax_id"),
        default_tax_id_2=data.get("default_tax_id_2"),
        notes=data.get("notes"),
    )
    g.session.add(contact)

    try:
        g.session.flush()

        # Create addresses if provided
        for addr_data in data.get("addresses", []):
            addr = ContactAddress(
                contact_id=contact.id,
                address_type=addr_data.get("address_type", "Address"),
                address_line_1=addr_data.get("address_line_1"),
                address_line_2=addr_data.get("address_line_2"),
                city=addr_data.get("city"),
                province_state=addr_data.get("province_state"),
                postal_code=addr_data.get("postal_code"),
                country=addr_data.get("country"),
            )
            g.session.add(addr)

        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    addrs = _get_addresses(g.session, contact.id)
    return jsonify(serialize_contact(contact, addresses=addrs)), 201


@bp.route("/contacts/<int:contact_id>", methods=["PUT"])
def update_contact(contact_id):
    contact = g.session.get(Contact, contact_id)
    if not contact:
        return jsonify(error="Contact not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    updatable = [
        "name", "contact_type", "company", "website", "email",
        "phone_1", "phone_1_label", "phone_2", "phone_2_label",
        "tax_number", "payment_terms", "default_tax_id", "default_tax_id_2",
        "notes",
    ]
    for field in updatable:
        if field in data:
            if field == "contact_type" and data[field] not in ("client", "supplier", "both"):
                return jsonify(error="contact_type must be client, supplier, or both"), 400
            setattr(contact, field, data[field])

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    addrs = _get_addresses(g.session, contact.id)
    return jsonify(serialize_contact(contact, addresses=addrs))


@bp.route("/contacts/<int:contact_id>", methods=["DELETE"])
def delete_contact(contact_id):
    contact = g.session.get(Contact, contact_id)
    if not contact:
        return jsonify(error="Contact not found"), 404

    contact.is_active = False

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Contact deactivated"), 200


# ── CSV Import ─────────────────────────────────────────────────────

# Fields that map from CSV columns to Contact model attributes
CONTACT_CSV_FIELDS = [
    "name", "contact_type", "company", "website", "email",
    "phone_1", "phone_1_label", "phone_2", "phone_2_label",
    "tax_number", "payment_terms", "notes",
    "address_line_1", "address_line_2", "city",
    "province_state", "postal_code", "country",
]


@bp.route("/contacts/import/preview", methods=["POST"])
def import_preview():
    """Parse a CSV and return its headers + sample rows for column mapping.

    Expects multipart/form-data with:
      - file: the CSV file
    Returns JSON: { headers: [...], sample_rows: [[...], ...], dynabooks_fields: [...] }
    """
    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return jsonify(error="File must be a .csv"), 400

    try:
        raw = file.stream.read().decode("utf-8-sig")
        stream = io.StringIO(raw)
        reader = csv.reader(stream)
        rows = list(reader)
    except Exception as e:
        return jsonify(error=f"Failed to read CSV: {e}"), 400

    if not rows:
        return jsonify(error="CSV file is empty"), 400

    headers = [h.strip() for h in rows[0]]
    sample_rows = rows[1:6]  # up to 5 sample rows

    # Try to auto-match headers to DynaBooks fields
    auto_map = {}
    normalized_fields = {f.lower().replace("_", " "): f for f in CONTACT_CSV_FIELDS}
    for i, h in enumerate(headers):
        norm = h.strip().lower().replace("_", " ").replace("/", " ")
        if norm in normalized_fields:
            auto_map[str(i)] = normalized_fields[norm]

    return jsonify({
        "headers": headers,
        "sample_rows": sample_rows,
        "dynabooks_fields": CONTACT_CSV_FIELDS,
        "auto_map": auto_map,
        "total_rows": len(rows) - 1,
    })


def _apply_column_map(row_values, headers, column_map):
    """Apply a column mapping to convert a CSV row into a DynaBooks field dict.

    column_map: dict mapping CSV column index (str) -> DynaBooks field name.
    row_values: list of values from the CSV row.
    """
    mapped = {}
    for col_idx_str, field_name in column_map.items():
        idx = int(col_idx_str)
        if 0 <= idx < len(row_values):
            mapped[field_name] = row_values[idx].strip() if row_values[idx] else ""
    return mapped


@bp.route("/contacts/import", methods=["POST"])
def import_contacts():
    """Import contacts from a CSV file.

    Expects multipart/form-data with:
      - file: the CSV file
      - contact_type (optional): override type for all rows (client/supplier/both)
      - column_map (optional): JSON string mapping CSV column indices to DynaBooks fields
        e.g. {"0": "name", "2": "email", "5": "city"}
    """
    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return jsonify(error="File must be a .csv"), 400

    override_type = request.form.get("contact_type")
    if override_type and override_type not in ("client", "supplier", "both"):
        return jsonify(error="contact_type must be client, supplier, or both"), 400

    # Parse optional column_map
    column_map = None
    column_map_raw = request.form.get("column_map")
    if column_map_raw:
        try:
            column_map = json.loads(column_map_raw)
        except (json.JSONDecodeError, TypeError):
            return jsonify(error="Invalid column_map JSON"), 400

    try:
        raw = file.stream.read().decode("utf-8-sig")
        stream = io.StringIO(raw)
    except Exception as e:
        return jsonify(error=f"Failed to read CSV: {e}"), 400

    if column_map:
        # Column-mapped mode: use csv.reader and apply mapping
        reader = csv.reader(stream)
        headers = next(reader, None)  # skip header row
        if not headers:
            return jsonify(error="CSV file is empty"), 400

        created = 0
        skipped = 0
        errors = []

        for row_num, row_values in enumerate(reader, start=2):
            row = _apply_column_map(row_values, headers, column_map)

            name = row.get("name", "")
            if not name:
                skipped += 1
                continue

            ct = override_type
            if not ct:
                raw_type = row.get("contact_type", "").lower()
                if raw_type in ("client", "supplier", "both"):
                    ct = raw_type
                else:
                    ct = "client"

            try:
                contact = Contact(
                    name=name,
                    contact_type=ct,
                    company=row.get("company", "") or None,
                    website=row.get("website", "") or None,
                    email=row.get("email", "") or None,
                    phone_1=row.get("phone_1", "") or None,
                    phone_1_label=row.get("phone_1_label", "") or None,
                    phone_2=row.get("phone_2", "") or None,
                    phone_2_label=row.get("phone_2_label", "") or None,
                    tax_number=row.get("tax_number", "") or None,
                    payment_terms=row.get("payment_terms", "") or "30 Days",
                    notes=row.get("notes", "") or None,
                )
                g.session.add(contact)
                g.session.flush()

                addr1 = row.get("address_line_1", "")
                city = row.get("city", "")
                if addr1 or city:
                    addr = ContactAddress(
                        contact_id=contact.id,
                        address_type="Mailing Address",
                        address_line_1=addr1 or None,
                        address_line_2=row.get("address_line_2", "") or None,
                        city=city or None,
                        province_state=row.get("province_state", "") or None,
                        postal_code=row.get("postal_code", "") or None,
                        country=row.get("country", "") or "CA",
                    )
                    g.session.add(addr)

                created += 1
            except Exception as e:
                errors.append(f"Row {row_num} ({name}): {e}")
                continue
    else:
        # Legacy mode: auto-match headers by normalised name
        reader = csv.DictReader(stream)

        if reader.fieldnames:
            reader.fieldnames = [
                f.strip().lower().replace(" ", "_").replace("/", "_")
                for f in reader.fieldnames
            ]

        created = 0
        skipped = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            row = {k: (v.strip() if v else "") for k, v in row.items()}

            name = row.get("name", "")
            if not name:
                skipped += 1
                continue

            ct = override_type
            if not ct:
                raw_type = row.get("contact_type", "").lower()
                if raw_type in ("client", "supplier", "both"):
                    ct = raw_type
                else:
                    ct = "client"

            try:
                contact = Contact(
                    name=name,
                    contact_type=ct,
                    company=row.get("company", "") or None,
                    website=row.get("website", "") or None,
                    email=row.get("email", "") or None,
                    phone_1=row.get("phone_1", "") or None,
                    phone_1_label=row.get("phone_1_label", "") or None,
                    phone_2=row.get("phone_2", "") or None,
                    phone_2_label=row.get("phone_2_label", "") or None,
                    tax_number=row.get("tax_number", "") or None,
                    payment_terms=row.get("payment_terms", "") or "30 Days",
                    notes=row.get("notes", "") or None,
                )
                g.session.add(contact)
                g.session.flush()

                addr1 = row.get("address_line_1", "")
                city = row.get("city", "")
                if addr1 or city:
                    addr = ContactAddress(
                        contact_id=contact.id,
                        address_type="Mailing Address",
                        address_line_1=addr1 or None,
                        address_line_2=row.get("address_line_2", "") or None,
                        city=city or None,
                        province_state=row.get("province_state", "") or None,
                        postal_code=row.get("postal_code", "") or None,
                        country=row.get("country", "") or "CA",
                    )
                    g.session.add(addr)

                created += 1
            except Exception as e:
                errors.append(f"Row {row_num} ({name}): {e}")
                continue

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=f"Database error: {e}"), 400

    result = {"created": created, "skipped": skipped}
    if errors:
        result["errors"] = errors
    return jsonify(result), 201


@bp.route("/contacts/import/template", methods=["GET"])
def import_template():
    """Return a CSV template with the expected column headers."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CONTACT_CSV_FIELDS)
    # Write one example row
    writer.writerow([
        "John Smith", "client", "Smith Corp", "https://smithcorp.ca",
        "john@smithcorp.ca", "555-0100", "Office", "555-0101", "Cell",
        "123456789", "30 Days", "",
        "123 Main St", "Suite 200", "Toronto",
        "ON", "M5V 1A1", "CA",
    ])

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts_template.csv"},
    )


# ── Address sub-routes ──────────────────────────────────────────────

@bp.route("/contacts/<int:contact_id>/addresses", methods=["GET"])
def list_addresses(contact_id):
    addrs = _get_addresses(g.session, contact_id)
    return jsonify([serialize_contact_address(a) for a in addrs])


@bp.route("/contacts/<int:contact_id>/addresses", methods=["POST"])
def create_address(contact_id):
    contact = g.session.get(Contact, contact_id)
    if not contact:
        return jsonify(error="Contact not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    addr = ContactAddress(
        contact_id=contact_id,
        address_type=data.get("address_type", "Address"),
        address_line_1=data.get("address_line_1"),
        address_line_2=data.get("address_line_2"),
        city=data.get("city"),
        province_state=data.get("province_state"),
        postal_code=data.get("postal_code"),
        country=data.get("country"),
    )
    g.session.add(addr)

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_contact_address(addr)), 201


@bp.route("/contacts/<int:contact_id>/addresses/<int:addr_id>", methods=["PUT"])
def update_address(contact_id, addr_id):
    addr = (
        g.session.query(ContactAddress)
        .filter(ContactAddress.id == addr_id, ContactAddress.contact_id == contact_id)
        .first()
    )
    if not addr:
        return jsonify(error="Address not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    for field in ["address_type", "address_line_1", "address_line_2",
                   "city", "province_state", "postal_code", "country"]:
        if field in data:
            setattr(addr, field, data[field])

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_contact_address(addr))


@bp.route("/contacts/<int:contact_id>/addresses/<int:addr_id>", methods=["DELETE"])
def delete_address(contact_id, addr_id):
    addr = (
        g.session.query(ContactAddress)
        .filter(ContactAddress.id == addr_id, ContactAddress.contact_id == contact_id)
        .first()
    )
    if not addr:
        return jsonify(error="Address not found"), 404

    try:
        g.session.delete(addr)
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Address deleted"), 200
