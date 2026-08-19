from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_logout_handler
from app.domain import LogoutCommand, Result

from ..current_user_provider import get_current_user_provider
from ..db_session import write_session

LogoutExecutorFn = Callable[[LogoutCommand], Awaitable[Result[None]]]


def get_logout_executor_fn(request: Request) -> LogoutExecutorFn:
    async def execute_fn(command: LogoutCommand) -> Result[None]:
        async with write_session(request) as session:
            handler = build_logout_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.handle(command)

    return execute_fn
