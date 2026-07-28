from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...entities import OtpChallenge


class OtpChallengeRepository(Protocol):
    async def invalidate_current_for_user(
        self
        , user_id: UUID
        , invalidated_at: datetime
    ) -> int:
        ...

    async def add(self, challenge: OtpChallenge) -> None:
        ...
