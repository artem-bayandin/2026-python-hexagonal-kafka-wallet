from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_list_admin_transactions_handler
from app.domain import AdminTransactionsQuery, PaginatedResult, Result, TransactionListItem

from ..db_session import read_session

ListAdminTransactionsExecutor = Callable[
    [AdminTransactionsQuery],
    Awaitable[Result[PaginatedResult[TransactionListItem]]],
]


def get_list_admin_transactions_executor(
    request: Request,
) -> ListAdminTransactionsExecutor:
    async def execute(
        query: AdminTransactionsQuery,
    ) -> Result[PaginatedResult[TransactionListItem]]:
        async with read_session(request) as session:
            handler = build_list_admin_transactions_handler(session)
            return await handler.handle(query)

    return execute
