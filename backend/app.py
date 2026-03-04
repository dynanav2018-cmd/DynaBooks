"""Flask application factory for DynaBooks."""

import json
import os
import sys
import time

from flask import Flask, g, jsonify, request, send_from_directory

from backend.config import make_session

# Shared heartbeat state (mutable dict so launcher can read it)
heartbeat_state = {"last": 0.0, "active": False}


def create_app(session_factory=None):
    """Create and configure the Flask application.

    Args:
        session_factory: Optional callable returning a session. Defaults
            to ``make_session``.  Pass a custom factory in tests to inject
            an in-memory session.
    """
    if session_factory is None:
        session_factory = make_session

    app = Flask(__name__)

    # ── Session management ──────────────────────────────────────────
    @app.before_request
    def open_session():
        # Multi-company support: if X-Company header is present, use
        # a per-company session.  Otherwise fall back to default.
        company_slug = request.headers.get("X-Company")
        if company_slug and session_factory is make_session:
            from backend.company_manager import make_company_session
            try:
                g.session = make_company_session(company_slug)
            except ValueError:
                g.session = session_factory()
        else:
            g.session = session_factory()

    @app.teardown_request
    def close_session(exc):
        # In test mode the caller manages the session lifetime.
        if app.config.get("TESTING"):
            return
        session = g.pop("session", None)
        if session is not None:
            session.close()

    # ── JSON error handlers ─────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error=str(e.description)), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Not found"), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify(error="Internal server error"), 500

    # ── Register blueprints ─────────────────────────────────────────
    from backend.routes.company import bp as company_bp
    from backend.routes.accounts import bp as accounts_bp
    from backend.routes.taxes import bp as taxes_bp
    from backend.routes.contacts import bp as contacts_bp
    from backend.routes.products import bp as products_bp
    from backend.routes.invoices import bp as invoices_bp
    from backend.routes.bills import bp as bills_bp
    from backend.routes.journals import bp as journals_bp
    from backend.routes.banking import bp as banking_bp
    from backend.routes.assignments import bp as assignments_bp
    from backend.routes.reports import bp as reports_bp
    from backend.routes.dashboard import bp as dashboard_bp
    from backend.routes.pdf import bp as pdf_bp
    from backend.routes.closing import bp as closing_bp
    from backend.routes.recurring_journals import bp as recurring_journals_bp
    from backend.routes.companies import bp as companies_bp

    app.register_blueprint(company_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(taxes_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(bills_bp)
    app.register_blueprint(journals_bp)
    app.register_blueprint(banking_bp)
    app.register_blueprint(assignments_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(closing_bp)
    app.register_blueprint(recurring_journals_bp)
    app.register_blueprint(companies_bp)

    # ── Build config endpoint ────────────────────────────────────────
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.dirname(__file__))

    _cfg_path = os.path.join(base_dir, 'build_config.json')
    if os.path.isfile(_cfg_path):
        with open(_cfg_path) as _f:
            _build_cfg = json.load(_f)
    else:
        _build_cfg = {"tier": "Light", "app_name": "DynaBooks Light"}

    @app.route("/api/build-config")
    def build_config():
        return jsonify(_build_cfg)

    # ── Browser heartbeat ──────────────────────────────────────────
    @app.route("/api/heartbeat", methods=["POST"])
    def heartbeat():
        heartbeat_state["last"] = time.time()
        heartbeat_state["active"] = True
        return jsonify(ok=True)

    @app.route("/api/shutdown", methods=["POST"])
    def shutdown():
        import threading
        threading.Timer(0.5, lambda: os._exit(0)).start()
        return jsonify(ok=True)

    # ── SPA static file serving ──────────────────────────────────────

    frontend_dist = os.path.join(base_dir, "frontend", "dist")

    if os.path.isdir(frontend_dist):
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_spa(path):
            file_path = os.path.join(frontend_dist, path)
            if path and os.path.isfile(file_path):
                return send_from_directory(frontend_dist, path)
            return send_from_directory(frontend_dist, "index.html")

    return app
