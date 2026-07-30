from collections.abc import AsyncIterator, Awaitable, Callable
import secrets
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.dependencies import (
    build_admin_deposit_handler,
    build_get_current_user_handler,
    build_list_currencies_handler,
    build_list_users_handler,
    build_logout_handler,
    build_request_otp_handler,
    build_verify_otp_handler,
)
from app.domain import (
    ADMIN_ACCESS_DENIED,
    AUTHENTICATION_FAILED,
    AdminDepositCommand,
    AdminDepositResult,
    CurrencyCatalogItem,
    CurrentUser,
    GetCurrentUserQuery,
    ListCurrenciesQuery,
    ListUsersQuery,
    LogoutCommand,
    RequestOtpCommand,
    RequestOtpResult,
    Result,
    UserReferenceItem,
    VerifyOtpCommand,
    VerifyOtpResult,
)

from .current_user_provider import ContextVarCurrentUserProvider
from .result_mapping import unwrap_result

# Bearer scheme

bearer_scheme = HTTPBearer(auto_error=False)

ADMIN_KEY_HEADER = "X-Admin-Key"

# Current user provider

_current_user_provider = ContextVarCurrentUserProvider()

# Current user executor

GetCurrentUserExecutor = Callable[[GetCurrentUserQuery], Awaitable[Result[CurrentUser]]]


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


# Logout executor

LogoutExecutor = Callable[[LogoutCommand], Awaitable[Result[None]]]


def get_logout_executor(request: Request) -> LogoutExecutor:
    async def execute(command: LogoutCommand) -> Result[None]:
        async with request.app.state.session_factory() as session, session.begin():
            handler = build_logout_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.handle(command)

    return execute


# Request OTP executor

RequestOtpExecutor = Callable[[RequestOtpCommand], Awaitable[Result[RequestOtpResult]]]


def get_request_otp_executor(request: Request) -> RequestOtpExecutor:
    async def execute(command: RequestOtpCommand) -> Result[RequestOtpResult]:
        async with request.app.state.session_factory() as session, session.begin():
            handler = build_request_otp_handler(
                session,
                request.app.state.settings,
            )
            return await handler.handle(command)

    return execute


# Verify OTP executor

VerifyOtpExecutor = Callable[[VerifyOtpCommand], Awaitable[Result[VerifyOtpResult]]]


def get_verify_otp_executor(request: Request) -> VerifyOtpExecutor:
    async def execute(command: VerifyOtpCommand) -> Result[VerifyOtpResult]:
        async with request.app.state.session_factory() as session, session.begin():
            handler = build_verify_otp_handler(
                session,
                request.app.state.settings,
            )
            return await handler.handle(command)

    return execute


# Authenticated request binding


async def bind_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    executor: Annotated[GetCurrentUserExecutor, Depends(get_current_user_executor)],
    provider: Annotated[
        ContextVarCurrentUserProvider,
        Depends(get_current_user_provider),
    ],
) -> AsyncIterator[None]:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        unwrap_result(Result.failure(AUTHENTICATION_FAILED))
    assert credentials is not None
    result = await executor(GetCurrentUserQuery(token=credentials.credentials))
    current_user = unwrap_result(result)
    # store user in a ContextVar for this request
    token = provider.bind(current_user)
    try:
        # hand off to the route handler (or next dependency)
        yield
    finally:
        # clean up after the request
        provider.reset(token)


# Reference auth


async def require_reference_auth(
    request: Request,
    x_admin_key: Annotated[str | None, Header(alias=ADMIN_KEY_HEADER)] = None,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> None:
    settings = request.app.state.settings
    if (
        x_admin_key is not None
        and settings.admin_api_key is not None
        and secrets.compare_digest(x_admin_key, settings.admin_api_key)
    ):
        return
    if credentials is not None and credentials.scheme.casefold() == "bearer":
        async with request.app.state.session_factory() as session:
            handler = build_get_current_user_handler(session, settings)
            result = await handler.handle(GetCurrentUserQuery(token=credentials.credentials))
            if result.is_success:
                return
    unwrap_result(Result.failure(AUTHENTICATION_FAILED))


# Admin auth


async def require_admin_key(
    request: Request,
    x_admin_key: Annotated[str | None, Header(alias=ADMIN_KEY_HEADER)] = None,
) -> None:
    settings = request.app.state.settings
    if settings.app_env != "development":
        unwrap_result(Result.failure(ADMIN_ACCESS_DENIED))
    if (
        x_admin_key is None
        or settings.admin_api_key is None
        or not secrets.compare_digest(x_admin_key, settings.admin_api_key)
    ):
        unwrap_result(Result.failure(ADMIN_ACCESS_DENIED))


# List currencies executor

ListCurrenciesExecutor = Callable[
    [ListCurrenciesQuery], Awaitable[Result[list[CurrencyCatalogItem]]]
]


def get_list_currencies_executor(request: Request) -> ListCurrenciesExecutor:
    async def execute(query: ListCurrenciesQuery) -> Result[list[CurrencyCatalogItem]]:
        async with request.app.state.session_factory() as session:
            handler = build_list_currencies_handler(session)
            return await handler.handle(query)

    return execute


# List users executor

ListUsersExecutor = Callable[[ListUsersQuery], Awaitable[Result[list[UserReferenceItem]]]]


def get_list_users_executor(request: Request) -> ListUsersExecutor:
    async def execute(query: ListUsersQuery) -> Result[list[UserReferenceItem]]:
        async with request.app.state.session_factory() as session:
            handler = build_list_users_handler(session)
            return await handler.handle(query)

    return execute


# Create admin deposit executor

AdminDepositExecutor = Callable[[AdminDepositCommand], Awaitable[Result[AdminDepositResult]]]


def get_admin_deposit_executor(request: Request) -> AdminDepositExecutor:
    async def execute(
        command: AdminDepositCommand,
    ) -> Result[AdminDepositResult]:
        async with request.app.state.session_factory() as session, session.begin():
            handler = build_admin_deposit_handler(session)
            return await handler.handle(command)

    return execute
