from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AdminWalletModel(Base):
    __tablename__ = "admin_wallets"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_admin_wallets_amount_nonnegative"),)

    currency_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
