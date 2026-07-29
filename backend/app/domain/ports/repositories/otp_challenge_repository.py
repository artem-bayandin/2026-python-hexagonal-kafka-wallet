from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...entities import OtpChallenge


class OtpChallengeRepository(Protocol):
    async def invalidate_current_for_user(self, user_id: UUID, invalidated_at: datetime) -> int: ...

    async def add(self, challenge: OtpChallenge) -> None: ...

    async def get_current_for_user_for_update(self, user_id: UUID) -> OtpChallenge | None: ...

    async def get_newest_by_digest_for_update(
        self, user_id: UUID, digest: str
    ) -> OtpChallenge | None: ...

    async def set_failed_attempt_count(self, challenge_id: UUID, count: int) -> None: ...

    async def mark_consumed(self, challenge_id: UUID, consumed_at: datetime) -> None: ...
