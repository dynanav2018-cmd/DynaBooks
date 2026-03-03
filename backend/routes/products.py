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

    product_type = request.args.get("type")
    if product_type in ("product", "recurring"):
        query = query.filter(Product.product_type == product_type)

    products = query.all()
    return jsonify([serialize_product(p) for p in products])


@bp.route("/products", methods=["POST"])
def create_product():
    data = request.get_json()
    if not data:
        return jsonify(error="Request body required"), 400

    name = data.get("name")
    if not name:
        return jsonify(error="name is required"), 400

    product_type = data.get("product_type", "product")
    if product_type not in ("product", "recurring"):
        return jsonify(error="product_type must be 'product' or 'recurring'"), 400

    if product_type == "product" and not data.get("revenue_account_id"):
        return jsonify(error="revenue_account_id is required for products"), 400
    if product_type == "recurring" and not data.get("expense_account_id"):
        return jsonify(error="expense_account_id is required for recurring expenses"), 400

    track_inventory = bool(data.get("track_inventory", False))
    if track_inventory:
        if not data.get("inventory_account_id"):
            return jsonify(error="inventory_account_id is required when tracking inventory"), 400
        if not data.get("cogs_account_id"):
            return jsonify(error="cogs_account_id is required when tracking inventory"), 400

    product = Product(
        name=name,
        description=data.get("description"),
        default_price=data.get("default_price", 0),
        product_type=product_type,
        revenue_account_id=data.get("revenue_account_id"),
        expense_account_id=data.get("expense_account_id"),
        tax_id=data.get("tax_id"),
        sku=data.get("sku"),
        track_inventory=track_inventory,
        reorder_point=data.get("reorder_point", 0),
        inventory_account_id=data.get("inventory_account_id"),
        cogs_account_id=data.get("cogs_account_id"),
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

    updatable = [
        "name", "description", "default_price", "revenue_account_id",
        "expense_account_id", "tax_id", "product_type",
        "sku", "track_inventory", "reorder_point",
        "inventory_account_id", "cogs_account_id",
    ]
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
