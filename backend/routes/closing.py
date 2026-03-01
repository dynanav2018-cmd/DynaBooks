"""Year-end closing routes."""

from flask import Blueprint, g, jsonify

from backend.services.closing import preview_closing, perform_closing

bp = Blueprint("closing", __name__, url_prefix="/api")


@bp.route("/closing/preview", methods=["GET"])
def closing_preview():
    try:
        result = preview_closing(g.session)
        if "error" in result:
            return jsonify(error=result["error"]), 400
        return jsonify(result)
    except Exception as e:
        return jsonify(error=str(e)), 400


@bp.route("/closing", methods=["POST"])
def closing_perform():
    try:
        result = perform_closing(g.session)
        return jsonify(result)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 500
