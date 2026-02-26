"""Company/Entity settings routes."""

from flask import Blueprint, g, jsonify, request

from python_accounting.models import Entity

from backend.serializers import serialize_entity

bp = Blueprint("company", __name__, url_prefix="/api")


@bp.route("/company", methods=["GET"])
def get_company():
    entity = g.session.entity
    if not entity:
        return jsonify(error="No entity configured"), 404
    return jsonify(serialize_entity(entity))


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

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 500

    return jsonify(serialize_entity(entity))
