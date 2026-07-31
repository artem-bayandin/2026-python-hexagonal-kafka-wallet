from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_verify_otp_handler
from app.domain import Result, VerifyOtpCommand, VerifyOtpResult

from ..db_session import write_session

VerifyOtpExecutor = Callable[[VerifyOtpCommand], Awaitable[Result[VerifyOtpResult]]]


def get_verify_otp_executor(request: Request) -> VerifyOtpExecutor:
    async def execute(command: VerifyOtpCommand) -> Result[VerifyOtpResult]:
        async with write_session(request) as session:
            handler = build_verify_otp_handler(
                session,
                request.app.state.settings,
            )
            return await handler.handle(command)

    return execute
