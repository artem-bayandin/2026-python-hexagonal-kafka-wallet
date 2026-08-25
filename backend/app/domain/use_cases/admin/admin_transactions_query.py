from dataclasses import dataclass

from ...ports import TransactionQueryRepository
from ...read_models import (
    AdminTransactionCursor,
    TransactionListItem,
    TransactionMapper,
)
from ...result import Result


@dataclass(frozen=True, slots=True)
class AdminTransactionsQuery:
    after: AdminTransactionCursor | None
    limit: int


class AdminTransactionsHandler:
    def __init__(self, transaction_query_repo: TransactionQueryRepository) -> None:
        self._transaction_query_repo = transaction_query_repo

    async def handle(self, query: AdminTransactionsQuery) -> Result[list[TransactionListItem]]:
        rows = await self._transaction_query_repo.list_all_transactions_after(
            query.after,
            query.limit,
        )
        items = [
            TransactionMapper.transaction_list_row_to_item(row, viewer_user_id=None) for row in rows
        ]
        return Result.success(items)
