from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_verify_otp_handler
from app.domain import Result, VerifyOtpCommand, VerifyOtpResult

from ..db_session import write_session

VerifyOtpExecutorFn = Callable[[VerifyOtpCommand], Awaitable[Result[VerifyOtpResult]]]


def get_verify_otp_executor_fn(request: Request) -> VerifyOtpExecutorFn:
    async def execute_fn(command: VerifyOtpCommand) -> Result[VerifyOtpResult]:
        async with write_session(request) as session:
            handler = build_verify_otp_handler(
                session,
                request.app.state.settings,
            )
            return await handler.handle(command)

    return execute_fn
