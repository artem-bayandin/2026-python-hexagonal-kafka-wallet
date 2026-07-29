from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: UUID
    session_jti: UUID
    expires_at: datetime
