from dataclasses import dataclass

from ...ports import CurrentUserProvider
from ...ports.repositories.user_wallet_query_repository import UserWalletQueryRepository
from ...read_models.balance_item import BalanceItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class GetUserBalancesQuery:
    pass


class GetUserBalancesHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        user_wallet_query_repo: UserWalletQueryRepository,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._user_wallet_query_repo = user_wallet_query_repo

    async def handle(self, _: GetUserBalancesQuery) -> Result[list[BalanceItem]]:
        user = self._current_user_provider.get()
        items = await self._user_wallet_query_repo.list_balances_for_user(user.id)
        return Result.success(items)
