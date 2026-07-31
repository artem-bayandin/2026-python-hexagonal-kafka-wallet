from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OtpChallengeItem:
    id: UUID
    user_id: UUID
    otp_digest: str
    expires_at: datetime
    failed_attempt_count: int
    consumed_at: datetime | None
    invalidated_at: datetime | None
    created_at: datetime
