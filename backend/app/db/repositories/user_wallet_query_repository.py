from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.domain import BalanceItem, UserWalletQueryRepository

from ..models import CurrencyModel, UserWalletModel
from ..session import AsyncSession


class UserWalletQueryRepositoryImpl(UserWalletQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_balances_for_user(self, user_id: UUID) -> list[BalanceItem]:
        stmt = (
            select(CurrencyModel.label, UserWalletModel.amount)
            .select_from(CurrencyModel)
            .outerjoin(
                UserWalletModel,
                (UserWalletModel.currency_id == CurrencyModel.id)
                & (UserWalletModel.user_id == user_id),
            )
            .order_by(CurrencyModel.label.asc())
        )
        result = await self.session.execute(stmt)
        return [
            BalanceItem(
                asset=row.label,
                available=row.amount if row.amount is not None else Decimal("0"),
            )
            for row in result.all()
        ]
