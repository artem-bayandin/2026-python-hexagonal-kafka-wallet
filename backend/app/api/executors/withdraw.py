from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_withdraw_handler
from app.domain import Result, WithdrawCommand, WithdrawResult

from ..current_user_provider import get_current_user_provider
from ..db_session import write_session

WithdrawExecutor = Callable[[WithdrawCommand], Awaitable[Result[WithdrawResult]]]


def get_withdraw_executor(request: Request) -> WithdrawExecutor:
    async def execute(command: WithdrawCommand) -> Result[WithdrawResult]:
        async with write_session(request) as session:
            handler = build_withdraw_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.handle(command)

    return execute
