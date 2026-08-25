from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_list_users_handler
from app.domain import Result, UserReferenceItem, UsersQuery

from ..db_session import read_session

ListUsersExecutorFn = Callable[[UsersQuery], Awaitable[Result[list[UserReferenceItem]]]]


def get_list_users_executor_fn(request: Request) -> ListUsersExecutorFn:
    async def execute_fn(query: UsersQuery) -> Result[list[UserReferenceItem]]:
        async with read_session(request) as session:
            handler = build_list_users_handler(session)
            return await handler.handle(query)

    return execute_fn
