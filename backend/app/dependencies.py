from app.auth import (
    HmacOtpService,
    PyJwtTokenService,
    SystemClock,
)
from app.config import KafkaSettings, ApiSettings
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
    CommandPublisher,
    CurrentUserProvider,
    ExchangeHandler,
    AdminBalancesHandler,
    CurrentUserHandler,
    UserBalancesHandler,
    AdminTransactionsHandler,
    CurrenciesHandler,
    UserTransactionsHandler,
    UsersHandler,
    LogoutHandler,
    RequestOtpHandler,
    TransferHandler,
    VerifyOtpHandler,
    WithdrawHandler,
    SubmitDepositHandler,
    SubmitWithdrawalHandler,
)
from app.kafka import build_kafka_command_publisher

# # # # Region: kafka

# CommandPublisher


def build_command_publisher(settings: KafkaSettings) -> CommandPublisher:
    return build_kafka_command_publisher(settings)


# # # # Region: routes.admin

# AdminDeposit (synchronous — retained for rollback reference only)


def build_admin_deposit_handler(
    session: AsyncSession,
) -> AdminDepositHandler:
    return AdminDepositHandler(
        UserQueryRepositoryImpl(session),
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )


def build_submit_deposit_handler(
    session: AsyncSession,
) -> SubmitDepositHandler:
    return SubmitDepositHandler(
        UserQueryRepositoryImpl(session),
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )


def build_submit_withdrawal_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> SubmitWithdrawalHandler:
    return SubmitWithdrawalHandler(
        current_user_provider,
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )


# GetAdminBalances


def build_get_admin_balances_handler(
    session: AsyncSession,
) -> AdminBalancesHandler:
    return AdminBalancesHandler(AdminWalletQueryRepositoryImpl(session))


# ListAdminTransactions


def build_list_admin_transactions_handler(
    session: AsyncSession,
) -> AdminTransactionsHandler:
    return AdminTransactionsHandler(TransactionQueryRepositoryImpl(session))


# # # # Region: routes.auth

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


# # # # Region: routes.currency

# ListCurrencies


def build_list_currencies_handler(session: AsyncSession) -> CurrenciesHandler:
    return CurrenciesHandler(CurrencyQueryRepositoryImpl(session))


# # # # Region: routes.otp

# RequestOTP


def build_request_otp_handler(
    session: AsyncSession,
    settings: ApiSettings,
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
    settings: ApiSettings,
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


# # # # Region: routes.user

# GetCurrentUser


def build_get_current_user_handler(
    session: AsyncSession,
    settings: ApiSettings,
) -> CurrentUserHandler:
    return CurrentUserHandler(
        PyJwtTokenService(settings.jwt_secret),
        SystemClock(),
        AuthSessionQueryRepositoryImpl(session),
        UserQueryRepositoryImpl(session),
    )


# ListUsers


def build_list_users_handler(session: AsyncSession) -> UsersHandler:
    return UsersHandler(UserQueryRepositoryImpl(session))


# GetUserBalances


def build_get_user_balances_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> UserBalancesHandler:
    return UserBalancesHandler(
        current_user_provider,
        UserWalletQueryRepositoryImpl(session),
    )


# ListUserTransactions


def build_list_user_transactions_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> UserTransactionsHandler:
    return UserTransactionsHandler(
        current_user_provider,
        TransactionQueryRepositoryImpl(session),
    )


# # # # Region: routes.wallet

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
        UserQueryRepositoryImpl(session),
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )
