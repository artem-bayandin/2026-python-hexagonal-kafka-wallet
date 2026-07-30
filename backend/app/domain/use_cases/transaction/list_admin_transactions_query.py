from dataclasses import dataclass

from ...ports.repositories.transaction_query_repository import TransactionQueryRepository
from ...read_models.pagination import PaginatedResult, PaginationParams
from ...read_models.transaction_list_item import TransactionListItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class ListAdminTransactionsQuery:
    params: PaginationParams


class ListAdminTransactionsHandler:
    def __init__(self, transaction_query_repo: TransactionQueryRepository) -> None:
        self._transaction_query_repo = transaction_query_repo

    async def handle(
        self, query: ListAdminTransactionsQuery
    ) -> Result[PaginatedResult[TransactionListItem]]:
        page = await self._transaction_query_repo.list_admin_page(query.params)
        return Result.success(page)
