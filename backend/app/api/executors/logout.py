from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_logout_handler
from app.domain import LogoutCommand, Result

from ..current_user_provider import get_current_user_provider
from ..db_session import write_session

LogoutExecutor = Callable[[LogoutCommand], Awaitable[Result[None]]]


def get_logout_executor(request: Request) -> LogoutExecutor:
    async def execute(command: LogoutCommand) -> Result[None]:
        async with write_session(request) as session:
            handler = build_logout_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.handle(command)

    return execute
