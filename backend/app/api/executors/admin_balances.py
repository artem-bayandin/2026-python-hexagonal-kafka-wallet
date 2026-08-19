from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_get_admin_balances_handler
from app.domain import AdminBalancesQuery, BalanceItem, Result

from ..db_session import read_session

AdminBalancesExecutorFn = Callable[[AdminBalancesQuery], Awaitable[Result[list[BalanceItem]]]]


def get_admin_balances_executor_fn(request: Request) -> AdminBalancesExecutorFn:
    async def execute_fn(query: AdminBalancesQuery) -> Result[list[BalanceItem]]:
        async with read_session(request) as session:
            handler = build_get_admin_balances_handler(session)
            return await handler.handle(query)

    return execute_fn
