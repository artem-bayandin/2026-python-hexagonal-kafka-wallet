from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_get_current_user_handler
from app.domain import CurrentUser, CurrentUserQuery, Result

from ..db_session import read_session

GetCurrentUserExecutor = Callable[[CurrentUserQuery], Awaitable[Result[CurrentUser]]]


def get_current_user_executor(request: Request) -> GetCurrentUserExecutor:
    async def execute(query: CurrentUserQuery) -> Result[CurrentUser]:
        async with read_session(request) as session:
            handler = build_get_current_user_handler(
                session,
                request.app.state.settings,
            )
            return await handler.handle(query)

    return execute
