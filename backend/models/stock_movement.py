"""Stock movement ledger for inventory tracking."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Integer, String, DateTime, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import CustomBase


class StockMovement(CustomBase):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity_change: Mapped[Decimal] = mapped_column(Numeric(13, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(13, 4), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(13, 4), nullable=False)
    quantity_after: Mapped[Decimal] = mapped_column(Numeric(13, 4), nullable=False)
    average_cost_after: Mapped[Decimal] = mapped_column(Numeric(13, 4), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class CogsJournalMap(CustomBase):
    """Maps an invoice transaction to its auto-created COGS journal entry."""
    __tablename__ = "cogs_journal_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_transaction_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    journal_transaction_id: Mapped[int] = mapped_column(Integer, nullable=False)
