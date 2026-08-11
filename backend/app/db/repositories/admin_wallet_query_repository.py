from decimal import Decimal

from sqlalchemy import select

from app.domain import AdminWalletQueryRepository, BalanceItem

from ..mappers import wallet_row_to_balance_item
from ..models import AdminWalletModel, CurrencyModel
from ..session import AsyncSession


class AdminWalletQueryRepositoryImpl(AdminWalletQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_admin_balances(self) -> list[BalanceItem]:
        stmt = (
            select(CurrencyModel.label, CurrencyModel.precision, AdminWalletModel.amount)
            .join(AdminWalletModel, AdminWalletModel.currency_id == CurrencyModel.id)
            .order_by(CurrencyModel.label.asc())
        )
        result = await self.session.execute(stmt)
        return [
            wallet_row_to_balance_item(row.label, row.amount, Decimal("0"), row.precision)
            for row in result.all()
        ]
