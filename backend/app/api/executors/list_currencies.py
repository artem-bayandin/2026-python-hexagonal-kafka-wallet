from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_list_currencies_handler
from app.domain import CurrenciesQuery, CurrencyCatalogItem, Result

from ..db_session import read_session

ListCurrenciesExecutorFn = Callable[[CurrenciesQuery], Awaitable[Result[list[CurrencyCatalogItem]]]]


def get_list_currencies_executor_fn(request: Request) -> ListCurrenciesExecutorFn:
    async def execute_fn(query: CurrenciesQuery) -> Result[list[CurrencyCatalogItem]]:
        async with read_session(request) as session:
            handler = build_list_currencies_handler(session)
            return await handler.handle(query)

    return execute_fn
