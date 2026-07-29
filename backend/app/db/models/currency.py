from uuid import UUID

from sqlalchemy import CheckConstraint, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CurrencyModel(Base):
    __tablename__ = "currencies"
    __table_args__ = (
        CheckConstraint(
            "type IN ('fiat', 'crypto')",
            name="ck_currencies_type_valid",
        ),
        CheckConstraint(
            "precision >= 0 AND precision <= 18",
            name="ck_currencies_precision_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    type: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(6), unique=True, nullable=False)
    precision: Mapped[int] = mapped_column(SmallInteger, nullable=False)
