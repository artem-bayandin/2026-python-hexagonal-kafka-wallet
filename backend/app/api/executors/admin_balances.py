from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_get_admin_balances_handler
from app.domain import AdminBalancesQuery, BalanceItem, Result

from ..db_session import read_session

GetAdminBalancesExecutor = Callable[[AdminBalancesQuery], Awaitable[Result[list[BalanceItem]]]]


def get_get_admin_balances_executor(request: Request) -> GetAdminBalancesExecutor:
    async def execute(query: AdminBalancesQuery) -> Result[list[BalanceItem]]:
        async with read_session(request) as session:
            handler = build_get_admin_balances_handler(session)
            return await handler.handle(query)

    return execute
