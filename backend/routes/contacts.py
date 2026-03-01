"""Client & Supplier contacts routes."""

from flask import Blueprint, g, jsonify, request

from backend.models.contact import Contact
from backend.serializers import serialize_contact

bp = Blueprint("contacts", __name__, url_prefix="/api")


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
    return jsonify([serialize_contact(c) for c in contacts])


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
        email=data.get("email"),
        phone=data.get("phone"),
        address_line_1=data.get("address_line_1"),
        address_line_2=data.get("address_line_2"),
        city=data.get("city"),
        province_state=data.get("province_state"),
        postal_code=data.get("postal_code"),
        country=data.get("country"),
        tax_number=data.get("tax_number"),
        payment_terms_days=data.get("payment_terms_days", 30),
        notes=data.get("notes"),
    )
    g.session.add(contact)

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_contact(contact)), 201


@bp.route("/contacts/<int:contact_id>", methods=["PUT"])
def update_contact(contact_id):
    contact = g.session.get(Contact, contact_id)
    if not contact:
        return jsonify(error="Contact not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    updatable = [
        "name", "contact_type", "email", "phone",
        "address_line_1", "address_line_2", "city", "province_state", "postal_code",
        "country", "tax_number", "payment_terms_days", "notes",
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

    return jsonify(serialize_contact(contact))


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
