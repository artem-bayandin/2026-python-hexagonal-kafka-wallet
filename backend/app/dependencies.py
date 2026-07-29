from fastapi import Request

from app.auth import (
    HmacOtpService,
    PyJwtTokenService,
    SystemClock,
)
from app.config import Settings
from app.db import (
    AsyncSession,
    AuthSessionRepositoryImpl,
    OtpChallengeRepositoryImpl,
    UserRepositoryImpl,
)
from app.domain import (
    CurrentUserProvider,
    GetCurrentUserHandler,
    LogoutHandler,
    RequestOtpCommand,
    RequestOtpResult,
    RequestOtpHandler,
    Result,
    VerifyOtpCommand,
    VerifyOtpHandler,
    VerifyOtpResult,
)

# GetCurrentUser


def build_get_current_user_handler(
    session: AsyncSession,
    settings: Settings,
) -> GetCurrentUserHandler:
    return GetCurrentUserHandler(
        PyJwtTokenService(settings.jwt_secret),
        SystemClock(),
        AuthSessionRepositoryImpl(session),
        UserRepositoryImpl(session),
    )


# Logout


def build_logout_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> LogoutHandler:
    return LogoutHandler(
        current_user_provider,
        AuthSessionRepositoryImpl(session),
        SystemClock(),
    )


# RequestOTP


def build_request_otp_handler(
    session: AsyncSession,
    settings: Settings,
) -> RequestOtpHandler:
    include_demo_otp = settings.app_env == "development" and settings.enable_demo_otp
    return RequestOtpHandler(
        UserRepositoryImpl(session),
        OtpChallengeRepositoryImpl(session),
        HmacOtpService(settings.otp_hmac_secret),
        SystemClock(),
        otp_ttl_seconds=settings.otp_ttl_seconds,
        include_demo_otp=include_demo_otp,
    )


async def execute_request_otp(
    request: Request,
    command: RequestOtpCommand,
) -> Result[RequestOtpResult]:
    async with request.app.state.session_factory() as session, session.begin():
        handler = build_request_otp_handler(
            session,
            request.app.state.settings,
        )
        return await handler.handle(command)


# VerifyOTP


def build_verify_otp_handler(
    session: AsyncSession,
    settings: Settings,
) -> VerifyOtpHandler:
    return VerifyOtpHandler(
        UserRepositoryImpl(session),
        OtpChallengeRepositoryImpl(session),
        AuthSessionRepositoryImpl(session),
        HmacOtpService(settings.otp_hmac_secret),
        PyJwtTokenService(settings.jwt_secret),
        SystemClock(),
        otp_max_attempts=settings.otp_max_attempts,
        access_token_ttl_minutes=settings.jwt_access_token_ttl_minutes,
    )


async def execute_verify_otp(
    request: Request,
    command: VerifyOtpCommand,
) -> Result[VerifyOtpResult]:
    async with request.app.state.session_factory() as session, session.begin():
        handler = build_verify_otp_handler(
            session,
            request.app.state.settings,
        )
        return await handler.handle(command)
