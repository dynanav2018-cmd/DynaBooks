"""Company address/contact info model."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models import CustomBase


class CompanyInfo(CustomBase):
    __tablename__ = "company_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    address_line_1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    province_state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
