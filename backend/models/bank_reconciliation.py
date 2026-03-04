"""Bank Reconciliation model."""

from datetime import datetime, timezone

from sqlalchemy import Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import CustomBase


class BankReconciliation(CustomBase):
    """Monthly bank reconciliation for a bank account."""
    __tablename__ = "bank_reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    statement_balance: Mapped[float] = mapped_column(Numeric(13, 4), default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, completed
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ReconciliationItem(CustomBase):
    """Individual transaction cleared in a reconciliation."""
    __tablename__ = "reconciliation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reconciliation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ledger_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_cleared: Mapped[bool] = mapped_column(Boolean, default=False)
