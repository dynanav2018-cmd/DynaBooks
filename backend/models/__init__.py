"""Custom models for DynaBooks (not provided by python-accounting)."""

from sqlalchemy.orm import DeclarativeBase


class CustomBase(DeclarativeBase):
    """Separate declarative base for custom tables.

    Lives alongside python-accounting's Base in the same SQLite database.
    """
    pass
