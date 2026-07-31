from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_transfer_handler
from app.domain import Result, TransferCommand, TransferResult

from ..current_user_provider import get_current_user_provider
from ..db_session import write_session

TransferExecutor = Callable[[TransferCommand], Awaitable[Result[TransferResult]]]


def get_transfer_executor(request: Request) -> TransferExecutor:
    async def execute(command: TransferCommand) -> Result[TransferResult]:
        async with write_session(request) as session:
            handler = build_transfer_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.handle(command)

    return execute
