from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_list_admin_transactions_handler
from app.domain import AdminTransactionsQuery, PaginatedResult, Result, TransactionListItem

from ..db_session import read_session

ListAdminTransactionsExecutorFn = Callable[
    [AdminTransactionsQuery], Awaitable[Result[PaginatedResult[TransactionListItem]]]
]


def get_list_admin_transactions_executor_fn(request: Request) -> ListAdminTransactionsExecutorFn:
    async def execute_fn(
        query: AdminTransactionsQuery,
    ) -> Result[PaginatedResult[TransactionListItem]]:
        async with read_session(request) as session:
            handler = build_list_admin_transactions_handler(session)
            return await handler.handle(query)

    return execute_fn
