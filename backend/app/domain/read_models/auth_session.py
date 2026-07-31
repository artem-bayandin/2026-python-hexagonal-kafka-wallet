from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthSessionItem:
    jti: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
