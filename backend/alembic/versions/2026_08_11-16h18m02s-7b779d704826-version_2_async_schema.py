"""version_2_async_schema

Revision ID: 7b779d704826
Revises: d377d8c90992
Create Date: 2026-08-11 16:18:02.687648

Lock-window note: indexes are created inside Alembic's transaction (not CONCURRENTLY).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b779d704826"
down_revision: Union[str, Sequence[str], None] = "d377d8c90992"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("transactions", sa.Column("request_id", sa.UUID(), nullable=True))
    op.execute(
        sa.text("UPDATE transactions SET request_id = gen_random_uuid() WHERE request_id IS NULL")
    )
    op.alter_column("transactions", "request_id", nullable=False)
    op.create_unique_constraint("uq_transactions_request_id", "transactions", ["request_id"])

    op.drop_constraint("ck_transactions_status_v1", "transactions", type_="check")
    op.execute(sa.text("UPDATE transactions SET status = 'succeeded' WHERE status = 'completed'"))
    op.create_check_constraint(
        "ck_transactions_status_v2",
        "transactions",
        "status IN ('submitted', 'pending', 'in_progress', 'succeeded', 'failed')",
    )

    op.add_column("transactions", sa.Column("error", sa.Text(), nullable=True))

    op.add_column(
        "transactions",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text("UPDATE transactions SET updated_at = created_at WHERE updated_at IS NULL"))
    op.alter_column("transactions", "updated_at", nullable=False)

    op.add_column(
        "user_wallets",
        sa.Column(
            "locked_amount",
            sa.Numeric(precision=28, scale=8),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_user_wallets_locked_amount_nonnegative",
        "user_wallets",
        "locked_amount >= 0",
    )
    op.create_check_constraint(
        "ck_user_wallets_spendable_nonnegative",
        "user_wallets",
        "amount - locked_amount >= 0",
    )

    op.create_index(
        "ix_transactions_status_created_at",
        "transactions",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_transactions_updated_at_id",
        "transactions",
        ["updated_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade is prohibited after Version 2-only data exists."""
    raise RuntimeError(
        "Downgrade from version_2_async_schema is prohibited after incompatible statuses "
        "(submitted, pending, in_progress) or non-zero locked_amount values exist. "
        "Use a reviewed forward-fix migration instead."
    )
