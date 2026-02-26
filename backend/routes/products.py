"""Product/Service catalog routes."""

from flask import Blueprint, g, jsonify, request

from backend.models.product import Product
from backend.serializers import serialize_product

bp = Blueprint("products", __name__, url_prefix="/api")


@bp.route("/products", methods=["GET"])
def list_products():
    query = g.session.query(Product)

    show_inactive = request.args.get("include_inactive")
    if not show_inactive:
        query = query.filter(Product.is_active == True)

    products = query.all()
    return jsonify([serialize_product(p) for p in products])


@bp.route("/products", methods=["POST"])
def create_product():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    name = data.get("name")
    revenue_account_id = data.get("revenue_account_id")

    if not name or not revenue_account_id:
        return jsonify(error="name and revenue_account_id are required"), 400

    product = Product(
        name=name,
        description=data.get("description"),
        default_price=data.get("default_price", 0),
        revenue_account_id=revenue_account_id,
        tax_id=data.get("tax_id"),
    )
    g.session.add(product)

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_product(product)), 201


@bp.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    product = g.session.get(Product, product_id)
    if not product:
        return jsonify(error="Product not found"), 404

    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    updatable = ["name", "description", "default_price", "revenue_account_id", "tax_id"]
    for field in updatable:
        if field in data:
            setattr(product, field, data[field])

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(serialize_product(product))


@bp.route("/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    product = g.session.get(Product, product_id)
    if not product:
        return jsonify(error="Product not found"), 404

    product.is_active = False

    try:
        g.session.commit()
    except Exception as e:
        g.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(message="Product deactivated"), 200
