from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from app.domain import OtpChallengeItem, OtpChallengeCommandRepository

from ..mappers import OtpChallengeDbMapper
from ..models import OtpChallengeModel
from ..session import AsyncSession


class OtpChallengeCommandRepositoryImpl(OtpChallengeCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def invalidate_current_for_user(self, user_id: UUID, invalidated_at: datetime) -> int:
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

    async def add(self, challenge: OtpChallengeItem) -> None:
        self.session.add(OtpChallengeDbMapper.to_model(challenge))

    async def get_current_for_user_for_update(self, user_id: UUID) -> OtpChallengeItem | None:
        stmt = (
            select(OtpChallengeModel)
            .where(
                OtpChallengeModel.user_id == user_id,
                OtpChallengeModel.consumed_at.is_(None),
                OtpChallengeModel.invalidated_at.is_(None),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return OtpChallengeDbMapper.to_domain(model)

    async def get_newest_by_digest_for_update(
        self, user_id: UUID, digest: str
    ) -> OtpChallengeItem | None:
        stmt = (
            select(OtpChallengeModel)
            .where(
                OtpChallengeModel.user_id == user_id,
                OtpChallengeModel.otp_digest == digest,
            )
            .order_by(
                OtpChallengeModel.created_at.desc(),
                OtpChallengeModel.id.desc(),
            )
            .limit(1)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return OtpChallengeDbMapper.to_domain(model)

    async def set_failed_attempt_count(self, challenge_id: UUID, count: int) -> None:
        stmt = (
            update(OtpChallengeModel)
            .where(OtpChallengeModel.id == challenge_id)
            .values(failed_attempt_count=count)
        )
        await self.session.execute(stmt)

    async def mark_consumed(self, challenge_id: UUID, consumed_at: datetime) -> None:
        stmt = (
            update(OtpChallengeModel)
            .where(OtpChallengeModel.id == challenge_id)
            .values(consumed_at=consumed_at)
        )
        await self.session.execute(stmt)
