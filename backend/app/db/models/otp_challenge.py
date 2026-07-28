from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OtpChallengeModel(Base):
    __tablename__ = "otp_challenges"
    __table_args__ = (
        # What it does: PostgreSQL rejects any row where failed_attempt_count is negative.
        # Why it exists: The column tracks how many wrong OTP codes were entered.
        # The app increments it on failed verification and compares it to a max (e.g. OTP_MAX_ATTEMPTS) to lock the challenge.
        # A negative value would be invalid and could break that logic.
        # The DB enforces the invariant even if application code has a bug.
        CheckConstraint(
            "failed_attempt_count >= 0",
            name="ck_otp_challenges_failed_attempt_count_nonnegative",
        ),
        # What it does: A composite B-tree index on (user_id, created_at DESC).
        # Why it exists: Most OTP queries are scoped to one user — e.g. “get the current challenge for this user”
        # or “list this user’s challenges, newest first.”
        # Indexing user_id first narrows to that user; created_at DESC matches “most recent first” without a separate sort.
        # This speeds up reads like get_current_for_user_for_update.
        # Note: text("created_at DESC") tells PostgreSQL to store the index in descending order on created_at.
        Index(
            "ix_otp_challenges_user_id_created_at",
            "user_id",
            text("created_at DESC"),
        ),
        # What it does: A partial unique index on user_id, but only for rows where both consumed_at and invalidated_at are NULL.
        # Why it exists: A challenge is “current” when it has not been consumed (successful verify)
        # or invalidated (replaced by a new OTP request).
        # The design allows many historical rows per user, but at most one active row at a time.
        # - After successful verification → consumed_at is set → row leaves the index → uniqueness no longer applies to it.
        # - When a new OTP is requested → old rows get invalidated_at set → same effect.
        # Concurrency: Together with locking the user row and invalidating before insert,
        # this prevents two concurrent requests from both leaving a “current” challenge for the same user.
        # If two transactions tried to insert current rows, one would hit a unique violation.
        Index(
            "uq_otp_challenges_one_current_per_user",
            "user_id",
            unique=True,
            postgresql_where=text(
                "consumed_at IS NULL AND invalidated_at IS NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType(as_uuid=True), primary_key=True)

    user_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    otp_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    failed_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
