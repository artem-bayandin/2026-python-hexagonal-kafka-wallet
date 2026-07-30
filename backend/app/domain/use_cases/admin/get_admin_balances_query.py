from dataclasses import dataclass

from ...ports.repositories.admin_wallet_query_repository import AdminWalletQueryRepository
from ...read_models.balance_item import BalanceItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class GetAdminBalancesQuery:
    pass


class GetAdminBalancesHandler:
    def __init__(self, admin_wallet_query_repo: AdminWalletQueryRepository) -> None:
        self._admin_wallet_query_repo = admin_wallet_query_repo

    async def handle(self, _: GetAdminBalancesQuery) -> Result[list[BalanceItem]]:
        items = await self._admin_wallet_query_repo.list_all_with_labels()
        return Result.success(items)
