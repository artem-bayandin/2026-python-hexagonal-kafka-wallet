from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update

from app.domain import UserWallet, UserWalletCommandRepository

from ..mappers import user_wallet_to_domain
from ..models import UserWalletModel
from ..session import AsyncSession


class UserWalletCommandRepositoryImpl(UserWalletCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_for_update(
        self, user_id: UUID, currency_id: UUID, wallet_id: UUID, now: datetime
    ) -> UserWallet:
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
                updated_at=now,
            )
            self.session.add(model)
            await self.session.flush()
            locked = await self.session.execute(
                select(UserWalletModel).where(UserWalletModel.id == model.id).with_for_update()
            )
            model = locked.scalar_one()
        return user_wallet_to_domain(model)

    async def credit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> None:
        stmt = (
            update(UserWalletModel)
            .where(UserWalletModel.id == wallet_id)
            .values(
                amount=UserWalletModel.amount + amount,
                updated_at=now,
            )
        )
        await self.session.execute(stmt)
