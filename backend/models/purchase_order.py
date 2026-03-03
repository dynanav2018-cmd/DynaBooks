"""Purchase order models for inventory procurement."""

from datetime import datetime, timezone, date
from decimal import Decimal

from sqlalchemy import Integer, String, Boolean, Date, DateTime, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import CustomBase


class PurchaseOrder(CustomBase):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    supplier_contact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PurchaseOrderLine(CustomBase):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(13, 4), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(13, 4), default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(13, 4), nullable=False)
    tax_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
