from dataclasses import dataclass

from ...ports import CurrentUserProvider, TransactionQueryRepository
from ...read_models import (
    PaginatedResult,
    PaginationParams,
    TransactionListItem,
    transaction_list_row_to_item,
)
from ...result import Result


@dataclass(frozen=True, slots=True)
class UserTransactionsQuery:
    params: PaginationParams


class UserTransactionsHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        transaction_query_repo: TransactionQueryRepository,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._transaction_query_repo = transaction_query_repo

    async def handle(
        self, query: UserTransactionsQuery
    ) -> Result[PaginatedResult[TransactionListItem]]:
        user = self._current_user_provider.get()
        page = await self._transaction_query_repo.get_user_transactions_page(user.id, query.params)
        items = [transaction_list_row_to_item(row, viewer_user_id=user.id) for row in page.items]
        return Result.success(PaginatedResult(total_items=page.total_items, items=items))
