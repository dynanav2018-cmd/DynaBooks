"""Company/Entity settings routes."""

import os

from flask import Blueprint, g, jsonify, request, send_file

from python_accounting.models import Entity

from backend.data_dir import get_logo_dir, get_logo_path, get_company_logo_path
from backend.models.company_info import CompanyInfo
from backend.serializers import serialize_entity, serialize_company_info

bp = Blueprint("company", __name__, url_prefix="/api")

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 MB

ADDRESS_FIELDS = [
    "address_line_1", "address_line_2", "city",
    "province_state", "postal_code", "country", "phone", "email",
]


@bp.route("/company", methods=["GET"])
def get_company():
    entity = g.session.entity
    if not entity:
        return jsonify(error="No entity configured"), 404

    result = serialize_entity(entity)

    info = g.session.query(CompanyInfo).filter(
        CompanyInfo.entity_id == entity.id
    ).first()
    result["company_info"] = serialize_company_info(info)

    return jsonify(result)


@bp.route("/company", methods=["PUT"])
def update_company():
    entity = g.session.entity
    if not entity:
        return jsonify(error="No entity configured"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    if "name" in data:
        entity.name = data["name"]
    if "locale" in data:
        entity.locale = data["locale"]

    # Handle company address info
    has_address_fields = any(f in data for f in ADDRESS_FIELDS)
    if has_address_fields:
        info = g.session.query(CompanyInfo).filter(
            CompanyInfo.entity_id == entity.id
        ).first()
        if not info:
            info = CompanyInfo(entity_id=entity.id)
            g.session.add(info)
        for field in ADDRESS_FIELDS:
            if field in data:
                setattr(info, field, data[field])

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 500

    result = serialize_entity(entity)
    info = g.session.query(CompanyInfo).filter(
        CompanyInfo.entity_id == entity.id
    ).first()
    result["company_info"] = serialize_company_info(info)
    return jsonify(result)


@bp.route("/company/logo", methods=["POST"])
def upload_logo():
    if "logo" not in request.files:
        return jsonify(error="No file part 'logo' in request"), 400
    file = request.files["logo"]
    if not file.filename:
        return jsonify(error="No file selected"), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify(error=f"File type {ext} not allowed. Use PNG or JPG."), 400

    data = file.read()
    if len(data) > MAX_LOGO_SIZE:
        return jsonify(error="File too large (max 2 MB)"), 400

    company_slug = request.headers.get("X-Company")
    logo_path = get_company_logo_path(company_slug) if company_slug else get_logo_path()
    with open(logo_path, "wb") as f:
        f.write(data)

    return jsonify(message="Logo uploaded"), 200


@bp.route("/company/logo", methods=["GET"])
def get_logo():
    company_slug = request.headers.get("X-Company")
    logo_path = get_company_logo_path(company_slug) if company_slug else get_logo_path()
    if not os.path.isfile(logo_path):
        return "", 204
    return send_file(logo_path, mimetype="image/png")
