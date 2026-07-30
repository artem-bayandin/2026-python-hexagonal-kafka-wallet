from app.auth import (
    HmacOtpService,
    PyJwtTokenService,
    SystemClock,
)
from app.config import Settings
from app.db import (
    AsyncSession,
    AuthSessionCommandRepositoryImpl,
    AuthSessionQueryRepositoryImpl,
    CurrencyQueryRepositoryImpl,
    OtpChallengeCommandRepositoryImpl,
    UserCommandRepositoryImpl,
    UserQueryRepositoryImpl,
)
from app.domain import (
    CurrentUserProvider,
    GetCurrentUserHandler,
    ListCurrenciesHandler,
    ListUsersHandler,
    LogoutHandler,
    RequestOtpHandler,
    VerifyOtpHandler,
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
