"""Join table linking transactions to contacts."""

from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import CustomBase


class TransactionContact(CustomBase):
    __tablename__ = "transaction_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True
    )
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contacts.id"), nullable=False
    )
