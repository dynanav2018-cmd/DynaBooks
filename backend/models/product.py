"""Product/Service catalog model."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Integer, String, Boolean, DateTime, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import CustomBase


class Product(CustomBase):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_price: Mapped[Decimal] = mapped_column(Numeric(13, 4), default=0)
    revenue_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
