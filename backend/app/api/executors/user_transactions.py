from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_list_user_transactions_handler
from app.domain import PaginatedResult, Result, TransactionListItem, UserTransactionsQuery

from ..db_session import read_session
from ..current_user_provider import get_current_user_provider

ListUserTransactionsExecutorFn = Callable[
    [UserTransactionsQuery], Awaitable[Result[PaginatedResult[TransactionListItem]]]
]


def get_list_user_transactions_executor_fn(request: Request) -> ListUserTransactionsExecutorFn:
    async def execute_fn(
        query: UserTransactionsQuery,
    ) -> Result[PaginatedResult[TransactionListItem]]:
        async with read_session(request) as session:
            handler = build_list_user_transactions_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.handle(query)

    return execute_fn
