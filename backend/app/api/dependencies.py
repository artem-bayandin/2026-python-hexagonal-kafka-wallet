from collections.abc import AsyncIterator
import secrets
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain import (
    ADMIN_ACCESS_DENIED,
    AUTHENTICATION_FAILED,
    CurrentUser,
    CurrentUserQuery,
    Result,
)

from .current_user_provider import ContextVarCurrentUserProvider, get_current_user_provider
from .executors import (
    AdminDepositExecutor,
    ExchangeExecutor,
    GetAdminBalancesExecutor,
    GetCurrentUserExecutor,
    GetUserBalancesExecutor,
    ListAdminTransactionsExecutor,
    ListCurrenciesExecutor,
    ListUserTransactionsExecutor,
    ListUsersExecutor,
    LogoutExecutor,
    RequestOtpExecutor,
    TransferExecutor,
    VerifyOtpExecutor,
    WithdrawExecutor,
    get_admin_deposit_executor_fn,
    get_current_user_executor,
    get_exchange_executor,
    get_get_admin_balances_executor,
    get_get_user_balances_executor,
    get_list_admin_transactions_executor,
    get_list_currencies_executor,
    get_list_user_transactions_executor,
    get_list_users_executor,
    get_logout_executor,
    get_request_otp_executor,
    get_transfer_executor,
    get_verify_otp_executor,
    get_withdraw_executor,
)
from .result_mapping import unwrap_domain_result

# Bearer scheme

bearer_scheme = HTTPBearer(auto_error=False)

ADMIN_KEY_HEADER = "X-Admin-Key"

# Authenticated request binding


async def _extract_current_user(
    executor: GetCurrentUserExecutor,
    http_credentials: HTTPAuthorizationCredentials | None,
) -> CurrentUser | None:
    if http_credentials is not None and http_credentials.scheme.casefold() == "bearer":
        result = await executor(CurrentUserQuery(token=http_credentials.credentials))
        current_user = unwrap_domain_result(result)
        return current_user
    return None


# auth: logout
# wallet: balances, txs, exch, withd, trnsfr
async def bind_current_user(
    http_credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    executor: Annotated[GetCurrentUserExecutor, Depends(get_current_user_executor)],
    current_user_provider: Annotated[
        ContextVarCurrentUserProvider, Depends(get_current_user_provider)
    ],
) -> AsyncIterator[None]:
    current_user = await _extract_current_user(executor, http_credentials)
    if current_user is None:
        unwrap_domain_result(Result.failure(AUTHENTICATION_FAILED))
    assert current_user is not None
    # store user in a ContextVar for this request
    token = current_user_provider.bind(current_user)
    try:
        # hand off to the route handler (or next dependency)
        yield
    finally:
        # clean up after the request
        current_user_provider.reset(token)


# Admin auth


# Not for import
def _valid_admin_key(x_admin_key: str | None, settings_admin_api_key: str | None) -> bool:
    return (
        x_admin_key is not None
        and settings_admin_api_key is not None
        and secrets.compare_digest(x_admin_key, settings_admin_api_key)
    )


# admin: depo, bal, txs
async def require_admin_key(
    request: Request,
    x_admin_key: Annotated[str | None, Header(alias=ADMIN_KEY_HEADER)] = None,
) -> None:
    settings = request.app.state.settings
    if settings.app_env != "development":
        unwrap_domain_result(Result.failure(ADMIN_ACCESS_DENIED))
    if not _valid_admin_key(x_admin_key, settings.admin_api_key):
        unwrap_domain_result(Result.failure(ADMIN_ACCESS_DENIED))


# Reference auth


# references: currencies, users
async def require_admin_or_user_auth(
    request: Request,
    http_credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    current_user_executor: Annotated[GetCurrentUserExecutor, Depends(get_current_user_executor)],
    x_admin_key: Annotated[str | None, Header(alias=ADMIN_KEY_HEADER)] = None,
) -> None:
    settings = request.app.state.settings
    # validate admin key
    if (
        # valid only id dev mode
        settings.app_env == "development" and _valid_admin_key(x_admin_key, settings.admin_api_key)
    ):
        # admin key exists and is valid
        return
    # validate user auth
    if await _extract_current_user(current_user_executor, http_credentials) is None:
        unwrap_domain_result(Result.failure(AUTHENTICATION_FAILED))


__all__ = [
    # Current file references
    "ADMIN_KEY_HEADER",
    "bearer_scheme",
    "bind_current_user",
    "require_admin_or_user_auth",
    "require_admin_key",
    # Executors
    "AdminDepositExecutor",
    "ExchangeExecutor",
    "GetAdminBalancesExecutor",
    "GetCurrentUserExecutor",
    "GetUserBalancesExecutor",
    "ListAdminTransactionsExecutor",
    "ListCurrenciesExecutor",
    "ListUserTransactionsExecutor",
    "ListUsersExecutor",
    "LogoutExecutor",
    "RequestOtpExecutor",
    "TransferExecutor",
    "VerifyOtpExecutor",
    "WithdrawExecutor",
    "get_admin_deposit_executor_fn",
    "get_current_user_executor",
    "get_current_user_provider",
    "get_exchange_executor",
    "get_get_admin_balances_executor",
    "get_get_user_balances_executor",
    "get_list_admin_transactions_executor",
    "get_list_currencies_executor",
    "get_list_user_transactions_executor",
    "get_list_users_executor",
    "get_logout_executor",
    "get_request_otp_executor",
    "get_transfer_executor",
    "get_verify_otp_executor",
    "get_withdraw_executor",
]
