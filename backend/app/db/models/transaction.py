from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('deposit', 'exchange', 'withdrawal', 'transfer')",
            name="ck_transactions_type_valid",
        ),
        CheckConstraint(
            "status IN ('submitted', 'pending', 'in_progress', 'succeeded', 'failed')",
            name="ck_transactions_status_v2",
        ),
        CheckConstraint(
            "(type = 'deposit' AND source_wallet_id IS NULL "
            "AND dest_wallet_id IS NOT NULL) OR "
            "(type = 'withdrawal' AND source_wallet_id IS NOT NULL "
            "AND dest_wallet_id IS NULL) OR "
            "(type IN ('exchange', 'transfer') AND source_wallet_id IS NOT NULL "
            "AND dest_wallet_id IS NOT NULL "
            "AND source_wallet_id <> dest_wallet_id)",
            name="ck_transactions_type_wallet_shape",
        ),
        CheckConstraint(
            "source_amount > 0 AND dest_amount > 0",
            name="ck_transactions_amounts_positive",
        ),
        Index(
            "ix_transactions_created_at_id",
            text("created_at DESC"),
            text("id DESC"),
        ),
        Index("ix_transactions_status_created_at", "status", "created_at"),
        Index("ix_transactions_updated_at_id", "updated_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        unique=True,
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_wallet_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_wallets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    dest_wallet_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_wallets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    dest_amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
