"""Recurring journal entry template model."""

from datetime import datetime, timezone

from sqlalchemy import Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import CustomBase


class RecurringJournal(CustomBase):
    __tablename__ = "recurring_journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    narration: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_items_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
