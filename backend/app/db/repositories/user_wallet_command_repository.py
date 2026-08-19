from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult

from app.domain import UserWalletItem, UserWalletCommandRepository

from ..mappers import UserWalletDbMapper
from ..models import UserWalletModel
from ..session import AsyncSession


class UserWalletCommandRepositoryImpl(UserWalletCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_for_update(
        self, user_id: UUID, currency_id: UUID, wallet_id: UUID, now: datetime
    ) -> UserWalletItem:
        stmt = (
            select(UserWalletModel)
            .where(
                UserWalletModel.user_id == user_id,
                UserWalletModel.currency_id == currency_id,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            model = UserWalletModel(
                id=wallet_id,
                user_id=user_id,
                currency_id=currency_id,
                amount=Decimal("0"),
                locked_amount=Decimal("0"),
                updated_at=now,
            )
            self.session.add(model)
            await self.session.flush()
            locked = await self.session.execute(
                select(UserWalletModel).where(UserWalletModel.id == model.id).with_for_update()
            )
            model = locked.scalar_one()
        return UserWalletDbMapper.to_domain(model)

    async def lock_for_update_ordered(self, wallet_ids: Sequence[UUID]) -> list[UserWalletItem]:
        ordered_ids = sorted(set(wallet_ids))
        stmt = (
            select(UserWalletModel)
            .where(UserWalletModel.id.in_(ordered_ids))
            .order_by(UserWalletModel.id.asc())
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return [UserWalletDbMapper.to_domain(row) for row in result.scalars().all()]

    async def credit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> bool:
        stmt = (
            update(UserWalletModel)
            .where(UserWalletModel.id == wallet_id)
            .values(
                amount=UserWalletModel.amount + amount,
                updated_at=now,
            )
        )
        result = cast(
            CursorResult[Any],
            await self.session.execute(stmt),
        )
        return result.rowcount > 0

    async def debit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> bool:
        stmt = (
            update(UserWalletModel)
            .where(
                UserWalletModel.id == wallet_id,
                UserWalletModel.amount >= amount,
            )
            .values(
                amount=UserWalletModel.amount - amount,
                updated_at=now,
            )
        )
        result = cast(
            CursorResult[Any],
            await self.session.execute(stmt),
        )
        return result.rowcount > 0

    async def reserve_debit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> bool:
        stmt = (
            update(UserWalletModel)
            .where(
                UserWalletModel.id == wallet_id,
                UserWalletModel.amount - UserWalletModel.locked_amount >= amount,
            )
            .values(
                locked_amount=UserWalletModel.locked_amount + amount,
                updated_at=now,
            )
        )
        result = cast(
            CursorResult[Any],
            await self.session.execute(stmt),
        )
        return result.rowcount > 0

    async def release_reservation(self, wallet_id: UUID, amount: Decimal, now: datetime) -> bool:
        stmt = (
            update(UserWalletModel)
            .where(
                UserWalletModel.id == wallet_id,
                UserWalletModel.locked_amount >= amount,
            )
            .values(
                locked_amount=UserWalletModel.locked_amount - amount,
                updated_at=now,
            )
        )
        result = cast(
            CursorResult[Any],
            await self.session.execute(stmt),
        )
        return result.rowcount > 0

    async def settle_debit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> bool:
        stmt = (
            update(UserWalletModel)
            .where(
                UserWalletModel.id == wallet_id,
                UserWalletModel.amount >= amount,
                UserWalletModel.locked_amount >= amount,
            )
            .values(
                amount=UserWalletModel.amount - amount,
                locked_amount=UserWalletModel.locked_amount - amount,
                updated_at=now,
            )
        )
        result = cast(
            CursorResult[Any],
            await self.session.execute(stmt),
        )
        return result.rowcount > 0
