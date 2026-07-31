from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_request_otp_handler
from app.domain import RequestOtpCommand, RequestOtpResult, Result

from ..db_session import write_session

RequestOtpExecutor = Callable[[RequestOtpCommand], Awaitable[Result[RequestOtpResult]]]


def get_request_otp_executor(request: Request) -> RequestOtpExecutor:
    async def execute(command: RequestOtpCommand) -> Result[RequestOtpResult]:
        async with write_session(request) as session:
            handler = build_request_otp_handler(
                session,
                request.app.state.settings,
            )
            return await handler.handle(command)

    return execute
