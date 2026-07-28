from fastapi import Request

from app.auth import HmacOtpService, SystemClock
from app.config import Settings
from app.db import (
    AsyncSession,
    OtpChallengeRepositoryImpl,
    UserRepositoryImpl,
)
from app.domain import (
    RequestOtpCommand,
    RequestOtpData,
    RequestOtpHandler,
    Result,
)


def build_request_otp_handler(
    session: AsyncSession,
    settings: Settings,
) -> RequestOtpHandler:
    include_demo_otp = (
        settings.app_env == "development" and settings.enable_demo_otp
    )
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
) -> Result[RequestOtpData]:
    async with request.app.state.session_factory() as session:
        async with session.begin():
            handler = build_request_otp_handler(
                session,
                request.app.state.settings,
            )
            return await handler.handle(command)
