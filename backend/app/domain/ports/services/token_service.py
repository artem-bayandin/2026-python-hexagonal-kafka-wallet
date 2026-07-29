from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...result import Result
from ...token_claims import TokenClaims


class TokenService(Protocol):
    def encode(self, user_id: UUID, session_jti: UUID, expires_at: datetime) -> str:
        ...

    def decode(self, token: str) -> Result[TokenClaims]:
        ...
