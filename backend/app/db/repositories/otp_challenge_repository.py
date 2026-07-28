from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.engine import CursorResult

from app.domain import OtpChallenge, OtpChallengeRepository

from ..mappers import otp_challenge_to_model
from ..models import OtpChallengeModel
from ..session import AsyncSession


class OtpChallengeRepositoryImpl(OtpChallengeRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def invalidate_current_for_user(
        self
        , user_id: UUID
        , invalidated_at: datetime
    ) -> int:
        stmt = (
            update(OtpChallengeModel)
            .where(
                OtpChallengeModel.user_id == user_id,
                OtpChallengeModel.consumed_at.is_(None),
                OtpChallengeModel.invalidated_at.is_(None),
            )
            .values(invalidated_at=invalidated_at)
        )
        result = cast(
            CursorResult[Any],
            await self.session.execute(stmt),
        )
        return result.rowcount

    async def add(self, challenge: OtpChallenge) -> None:
        self.session.add(otp_challenge_to_model(challenge))
