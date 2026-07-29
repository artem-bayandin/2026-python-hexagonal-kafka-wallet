from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .current_user_provider import ContextVarCurrentUserProvider
from .result_mapping import unwrap_result
from app.dependencies import build_get_current_user_handler
from app.domain import (
    AUTHENTICATION_FAILED,
    CurrentUser,
    GetCurrentUserQuery,
    Result,
)

bearer_scheme = HTTPBearer(auto_error=False)

_current_user_provider = ContextVarCurrentUserProvider()

GetCurrentUserExecutor = Callable[
    [GetCurrentUserQuery], Awaitable[Result[CurrentUser]]
]


def get_current_user_provider() -> ContextVarCurrentUserProvider:
    return _current_user_provider


def get_current_user_executor(request: Request) -> GetCurrentUserExecutor:
    async def execute(query: GetCurrentUserQuery) -> Result[CurrentUser]:
        async with request.app.state.session_factory() as session:
            handler = build_get_current_user_handler(
                session,
                request.app.state.settings,
            )
            return await handler.handle(query)

    return execute


async def bind_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    executor: Annotated[
        GetCurrentUserExecutor, Depends(get_current_user_executor)
    ],
    provider: Annotated[
        ContextVarCurrentUserProvider,
        Depends(get_current_user_provider),
    ],
) -> AsyncIterator[None]:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        unwrap_result(Result.failure(AUTHENTICATION_FAILED))
    assert credentials is not None
    result = await executor(
        GetCurrentUserQuery(token=credentials.credentials)
    )
    current_user = unwrap_result(result)
    # store user in a ContextVar for this request
    token = provider.bind(current_user)
    try:
        # hand off to the route handler (or next dependency)
        yield
    finally:
        # clean up after the request
        provider.reset(token)
