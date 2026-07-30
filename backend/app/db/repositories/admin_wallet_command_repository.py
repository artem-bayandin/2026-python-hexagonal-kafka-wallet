from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update

from app.domain import AdminWalletCommandRepository

from ..models import AdminWalletModel
from ..session import AsyncSession


class AdminWalletCommandRepositoryImpl(AdminWalletCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_update(self, currency_id: UUID) -> None:
        stmt = (
            select(AdminWalletModel)
            .where(AdminWalletModel.currency_id == currency_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        result.scalar_one()

    async def credit(self, currency_id: UUID, amount: Decimal, now: datetime) -> None:
        stmt = (
            update(AdminWalletModel)
            .where(AdminWalletModel.currency_id == currency_id)
            .values(
                amount=AdminWalletModel.amount + amount,
                updated_at=now,
            )
        )
        await self.session.execute(stmt)
