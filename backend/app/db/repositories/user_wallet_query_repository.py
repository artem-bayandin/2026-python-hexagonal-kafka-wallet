from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.domain import BalanceItem, UserWalletQueryRepository

from ..mappers import wallet_row_to_balance_item
from ..models import CurrencyModel, UserWalletModel
from ..session import AsyncSession


class UserWalletQueryRepositoryImpl(UserWalletQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_balances(self, user_id: UUID) -> list[BalanceItem]:
        stmt = (
            select(
                CurrencyModel.label,
                CurrencyModel.precision,
                UserWalletModel.amount,
                UserWalletModel.locked_amount,
            )
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
            wallet_row_to_balance_item(
                row.label,
                row.amount if row.amount is not None else Decimal("0"),
                row.locked_amount if row.locked_amount is not None else Decimal("0"),
                row.precision,
            )
            for row in result.all()
        ]
