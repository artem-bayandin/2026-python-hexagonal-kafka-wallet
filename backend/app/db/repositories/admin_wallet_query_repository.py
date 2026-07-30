from sqlalchemy import select

from app.domain import AdminWalletQueryRepository, BalanceItem

from ..mappers import admin_wallet_row_to_balance_item
from ..models import AdminWalletModel, CurrencyModel
from ..session import AsyncSession


class AdminWalletQueryRepositoryImpl(AdminWalletQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all_with_labels(self) -> list[BalanceItem]:
        stmt = (
            select(CurrencyModel.label, AdminWalletModel.amount)
            .join(AdminWalletModel, AdminWalletModel.currency_id == CurrencyModel.id)
            .order_by(CurrencyModel.label.asc())
        )
        result = await self.session.execute(stmt)
        return [admin_wallet_row_to_balance_item(row.label, row.amount) for row in result.all()]
