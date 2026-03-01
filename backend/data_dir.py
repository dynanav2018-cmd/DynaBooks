"""Resolve data directory for DynaBooks storage (database, logos, etc.)."""

import json
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_FILE = os.path.join(_project_root, "dynabooks.json")


def _is_frozen():
    """Return True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def _default_data_dir():
    """Return the default data directory.

    When running as a PyInstaller EXE, stores data next to the EXE so that
    Dropbox (or any shared folder) syncs both app and data together.
    When running from source, defaults to <project_root>/data.
    """
    if _is_frozen():
        return os.path.join(os.path.dirname(sys.executable), "data")
    return os.path.join(_project_root, "data")


def get_data_dir():
    """Return the configured data directory path, creating it if needed.

    Reads from ``dynabooks.json`` (next to project root).  Falls back to
    ``_default_data_dir()``.
    """
    data_dir = _default_data_dir()

    if os.path.isfile(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            if cfg.get("data_dir"):
                data_dir = cfg["data_dir"]
        except (json.JSONDecodeError, OSError):
            pass

    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_db_path():
    """Return the full path to the SQLite database file."""
    return os.path.join(get_data_dir(), "dynabooks.db")


def get_logo_dir():
    """Return the path to the logos directory, creating it if needed."""
    logo_dir = os.path.join(get_data_dir(), "logos")
    os.makedirs(logo_dir, exist_ok=True)
    return logo_dir


def get_logo_path():
    """Return the path to the company logo file (may not exist)."""
    return os.path.join(get_logo_dir(), "logo.png")


# ── Multi-company paths ─────────────────────────────────────────

def get_companies_file():
    """Return path to the companies registry JSON file."""
    return os.path.join(get_data_dir(), "companies.json")


def get_company_dir(slug):
    """Return the data directory for a specific company."""
    company_dir = os.path.join(get_data_dir(), slug)
    os.makedirs(company_dir, exist_ok=True)
    return company_dir


def get_company_db_path(slug):
    """Return the SQLite database path for a specific company."""
    return os.path.join(get_company_dir(slug), "dynabooks.db")


def get_company_logo_dir(slug):
    """Return the logo directory for a specific company."""
    logo_dir = os.path.join(get_company_dir(slug), "logos")
    os.makedirs(logo_dir, exist_ok=True)
    return logo_dir


def get_company_logo_path(slug):
    """Return the logo file path for a specific company."""
    return os.path.join(get_company_logo_dir(slug), "logo.png")
