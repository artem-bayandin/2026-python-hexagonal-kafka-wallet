from dataclasses import dataclass

from ...ports import TransactionQueryRepository
from ...read_models import (
    PaginatedResult,
    PaginationParams,
    TransactionListItem,
    TransactionMapper,
)
from ...result import Result


@dataclass(frozen=True, slots=True)
class AdminTransactionsQuery:
    params: PaginationParams


class AdminTransactionsHandler:
    def __init__(self, transaction_query_repo: TransactionQueryRepository) -> None:
        self._transaction_query_repo = transaction_query_repo

    async def handle(
        self, query: AdminTransactionsQuery
    ) -> Result[PaginatedResult[TransactionListItem]]:
        page = await self._transaction_query_repo.get_all_transactions_page(query.params)
        items = [
            TransactionMapper.transaction_list_row_to_item(row, viewer_user_id=None)
            for row in page.items
        ]
        return Result.success(PaginatedResult(total_items=page.total_items, items=items))
