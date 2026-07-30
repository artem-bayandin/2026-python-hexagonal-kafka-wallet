from dataclasses import dataclass

from ...ports import CurrentUserProvider
from ...ports.repositories.transaction_query_repository import (
    TransactionQueryRepository,
)
from ...read_models.pagination import PaginatedResult, PaginationParams
from ...read_models.transaction_list_item import TransactionListItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class ListUserTransactionsQuery:
    params: PaginationParams


class ListUserTransactionsHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        transaction_query_repo: TransactionQueryRepository,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._transaction_query_repo = transaction_query_repo

    async def handle(
        self, query: ListUserTransactionsQuery
    ) -> Result[PaginatedResult[TransactionListItem]]:
        user = self._current_user_provider.get()
        page = await self._transaction_query_repo.list_user_page(user.id, query.params)
        return Result.success(page)
