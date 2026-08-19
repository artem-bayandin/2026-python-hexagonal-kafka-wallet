from dataclasses import dataclass

from ...ports import CurrentUserProvider, UserWalletQueryRepository
from ...read_models import BalanceItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class UserBalancesQuery:
    pass


class UserBalancesHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        user_wallet_query_repo: UserWalletQueryRepository,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._user_wallet_query_repo = user_wallet_query_repo

    async def handle(self, _: UserBalancesQuery) -> Result[list[BalanceItem]]:
        user = self._current_user_provider.get()
        items = await self._user_wallet_query_repo.get_user_balances(user.id)
        return Result.success(items)
