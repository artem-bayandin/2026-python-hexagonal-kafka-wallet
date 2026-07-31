from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_admin_deposit_handler
from app.domain import AdminDepositCommand, AdminDepositResult, Result

from ..db_session import write_session

AdminDepositExecutor = Callable[[AdminDepositCommand], Awaitable[Result[AdminDepositResult]]]


def get_admin_deposit_executor(request: Request) -> AdminDepositExecutor:
    async def execute(
        command: AdminDepositCommand,
    ) -> Result[AdminDepositResult]:
        async with write_session(request) as session:
            handler = build_admin_deposit_handler(session)
            return await handler.handle(command)

    return execute
