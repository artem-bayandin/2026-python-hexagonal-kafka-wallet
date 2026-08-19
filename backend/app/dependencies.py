from app.auth import (
    HmacOtpService,
    PyJwtTokenService,
    SystemClock,
)
from aiokafka import AIOKafkaProducer

from app.config import KafkaSettings, ApiSettings
from app.db import (
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
    CommandPublisher,
    CurrentUserProvider,
    AdminBalancesHandler,
    CurrentUserHandler,
    UserBalancesHandler,
    AdminTransactionsHandler,
    CurrenciesHandler,
    UserTransactionsHandler,
    UsersHandler,
    LogoutHandler,
    RequestOtpHandler,
    VerifyOtpHandler,
    SubmitDepositHandler,
    SubmitExchangeHandler,
    SubmitTransferHandler,
    SubmitWithdrawalHandler,
)
from app.kafka import build_kafka_command_publisher

# # # # Region: kafka

# CommandPublisher


def build_command_publisher(
    settings: KafkaSettings,
    producer: AIOKafkaProducer | None = None,
) -> CommandPublisher:
    return build_kafka_command_publisher(settings, producer=producer)


# # # # Region: routes.admin

# AdminDeposit


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


def build_submit_exchange_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> SubmitExchangeHandler:
    return SubmitExchangeHandler(
        current_user_provider,
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )


# Withdraw


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


# Transfer


def build_submit_transfer_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> SubmitTransferHandler:
    return SubmitTransferHandler(
        current_user_provider,
        UserQueryRepositoryImpl(session),
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )
