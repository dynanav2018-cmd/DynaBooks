"""Contact model for clients and suppliers."""

from datetime import datetime, timezone

from sqlalchemy import Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import CustomBase


class Contact(CustomBase):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "client", "supplier", or "both"
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone_1: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone_1_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_2: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone_2_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_line_1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    province_state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    payment_terms: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default="30 Days"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ContactAddress(CustomBase):
    """Multiple addresses per contact (Mailing, Office, Shipping, Home, etc.)."""
    __tablename__ = "contact_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    address_type: Mapped[str] = mapped_column(String(30), nullable=False)
    address_line_1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    province_state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TransactionAddress(CustomBase):
    """Stores billing/shipping address selections for invoices and bills."""
    __tablename__ = "transaction_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    billing_address_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_address_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
