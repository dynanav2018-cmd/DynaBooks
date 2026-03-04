"""Client & Supplier contacts routes."""

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
        "tax_number", "payment_terms", "notes",
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
