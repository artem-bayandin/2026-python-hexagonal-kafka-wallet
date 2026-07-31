from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_exchange_handler
from app.domain import ExchangeCommand, ExchangeResult, Result

from ..current_user_provider import get_current_user_provider
from ..db_session import write_session

ExchangeExecutor = Callable[[ExchangeCommand], Awaitable[Result[ExchangeResult]]]


def get_exchange_executor(request: Request) -> ExchangeExecutor:
    async def execute(command: ExchangeCommand) -> Result[ExchangeResult]:
        async with write_session(request) as session:
            handler = build_exchange_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.handle(command)

    return execute
