from dataclasses import dataclass

from ...ports import AdminWalletQueryRepository
from ...read_models import BalanceItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class AdminBalancesQuery:
    pass


class AdminBalancesHandler:
    def __init__(self, admin_wallet_query_repo: AdminWalletQueryRepository) -> None:
        self._admin_wallet_query_repo = admin_wallet_query_repo

    async def handle(self, _: AdminBalancesQuery) -> Result[list[BalanceItem]]:
        items = await self._admin_wallet_query_repo.get_admin_balances()
        return Result.success(items)
