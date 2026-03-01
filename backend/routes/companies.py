"""Multi-company management routes."""

from flask import Blueprint, jsonify, request

from backend.company_manager import list_companies, get_company, create_company

bp = Blueprint("companies", __name__, url_prefix="/api")


@bp.route("/companies", methods=["GET"])
def list_all():
    return jsonify(list_companies())


@bp.route("/companies", methods=["POST"])
def create():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify(error="Company name is required"), 400

    name = data["name"]
    year_start = data.get("year_start", 1)
    locale = data.get("locale", "en_CA")

    try:
        company = create_company(name, year_start=year_start, locale=locale)
        return jsonify(company), 201
    except Exception as e:
        return jsonify(error=str(e)), 500


@bp.route("/companies/<slug>", methods=["GET"])
def get_one(slug):
    company = get_company(slug)
    if not company:
        return jsonify(error="Company not found"), 404
    return jsonify(company)
