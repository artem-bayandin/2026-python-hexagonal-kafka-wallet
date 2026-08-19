from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_get_user_balances_handler
from app.domain import BalanceItem, Result, UserBalancesQuery

from ..db_session import read_session
from ..current_user_provider import get_current_user_provider

GetUserBalancesExecutorFn = Callable[[UserBalancesQuery], Awaitable[Result[list[BalanceItem]]]]


def get_user_balances_executor_fn(request: Request) -> GetUserBalancesExecutorFn:
    async def execute_fn(query: UserBalancesQuery) -> Result[list[BalanceItem]]:
        async with read_session(request) as session:
            handler = build_get_user_balances_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.handle(query)

    return execute_fn
