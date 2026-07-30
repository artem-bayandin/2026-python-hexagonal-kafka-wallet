from app.auth import (
    HmacOtpService,
    PyJwtTokenService,
    SystemClock,
)
from app.config import Settings
from app.db import (
    AdminWalletCommandRepositoryImpl,
    AdminWalletQueryRepositoryImpl,
    AsyncSession,
    AuthSessionCommandRepositoryImpl,
    AuthSessionQueryRepositoryImpl,
    CurrencyQueryRepositoryImpl,
    OtpChallengeCommandRepositoryImpl,
    TransactionCommandRepositoryImpl,
    TransactionQueryRepositoryImpl,
    UserCommandRepositoryImpl,
    UserQueryRepositoryImpl,
    UserWalletCommandRepositoryImpl,
    UserWalletQueryRepositoryImpl,
)
from app.domain import (
    AdminDepositHandler,
    CurrentUserProvider,
    ExchangeHandler,
    GetAdminBalancesHandler,
    GetCurrentUserHandler,
    GetUserBalancesHandler,
    ListAdminTransactionsHandler,
    ListCurrenciesHandler,
    ListUserTransactionsHandler,
    ListUsersHandler,
    LogoutHandler,
    RequestOtpHandler,
    TransferHandler,
    VerifyOtpHandler,
    WithdrawHandler,
)

# GetCurrentUser


def build_get_current_user_handler(
    session: AsyncSession,
    settings: Settings,
) -> GetCurrentUserHandler:
    return GetCurrentUserHandler(
        PyJwtTokenService(settings.jwt_secret),
        SystemClock(),
        AuthSessionQueryRepositoryImpl(session),
        UserQueryRepositoryImpl(session),
    )


# Logout


def build_logout_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> LogoutHandler:
    return LogoutHandler(
        current_user_provider,
        AuthSessionCommandRepositoryImpl(session),
        SystemClock(),
    )


# RequestOTP


def build_request_otp_handler(
    session: AsyncSession,
    settings: Settings,
) -> RequestOtpHandler:
    include_demo_otp = settings.app_env == "development" and settings.enable_demo_otp
    return RequestOtpHandler(
        UserCommandRepositoryImpl(session),
        OtpChallengeCommandRepositoryImpl(session),
        HmacOtpService(settings.otp_hmac_secret),
        SystemClock(),
        otp_ttl_seconds=settings.otp_ttl_seconds,
        include_demo_otp=include_demo_otp,
    )


# VerifyOTP


def build_verify_otp_handler(
    session: AsyncSession,
    settings: Settings,
) -> VerifyOtpHandler:
    return VerifyOtpHandler(
        UserCommandRepositoryImpl(session),
        OtpChallengeCommandRepositoryImpl(session),
        AuthSessionCommandRepositoryImpl(session),
        HmacOtpService(settings.otp_hmac_secret),
        PyJwtTokenService(settings.jwt_secret),
        SystemClock(),
        otp_max_attempts=settings.otp_max_attempts,
        access_token_ttl_minutes=settings.jwt_access_token_ttl_minutes,
    )


# ListCurrencies


def build_list_currencies_handler(session: AsyncSession) -> ListCurrenciesHandler:
    return ListCurrenciesHandler(CurrencyQueryRepositoryImpl(session))


# ListUsers


def build_list_users_handler(session: AsyncSession) -> ListUsersHandler:
    return ListUsersHandler(UserQueryRepositoryImpl(session))


# AdminDeposit


def build_admin_deposit_handler(
    session: AsyncSession,
) -> AdminDepositHandler:
    return AdminDepositHandler(
        UserCommandRepositoryImpl(session),
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )


# GetAdminBalances


def build_get_admin_balances_handler(
    session: AsyncSession,
) -> GetAdminBalancesHandler:
    return GetAdminBalancesHandler(AdminWalletQueryRepositoryImpl(session))


# ListAdminTransactions


def build_list_admin_transactions_handler(
    session: AsyncSession,
) -> ListAdminTransactionsHandler:
    return ListAdminTransactionsHandler(TransactionQueryRepositoryImpl(session))


# GetUserBalances


def build_get_user_balances_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> GetUserBalancesHandler:
    return GetUserBalancesHandler(
        current_user_provider,
        UserWalletQueryRepositoryImpl(session),
    )


# ListUserTransactions


def build_list_user_transactions_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> ListUserTransactionsHandler:
    return ListUserTransactionsHandler(
        current_user_provider,
        TransactionQueryRepositoryImpl(session),
    )


# Exchange


def build_exchange_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> ExchangeHandler:
    return ExchangeHandler(
        current_user_provider,
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )


# Withdraw


def build_withdraw_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> WithdrawHandler:
    return WithdrawHandler(
        current_user_provider,
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        AdminWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )


# Transfer


def build_transfer_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> TransferHandler:
    return TransferHandler(
        current_user_provider,
        UserCommandRepositoryImpl(session),
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )
