from collections.abc import Awaitable, Callable

from fastapi import Request

from app.db import AsyncSession
from app.dependencies import build_submit_deposit_handler
from app.domain import AdminDepositCommand, Result, SubmissionInterimHandlerResult, SubmissionResult

from .submission import get_submission_executor_fn

AdminDepositExecutorFn = Callable[[AdminDepositCommand], Awaitable[Result[SubmissionResult]]]


def get_admin_deposit_executor_fn(request: Request) -> AdminDepositExecutorFn:
    submission_executor_fn = get_submission_executor_fn(request)

    async def execute_fn(command: AdminDepositCommand) -> Result[SubmissionResult]:
        async def handle_submit_deposit_fn(
            session: AsyncSession,
        ) -> Result[SubmissionInterimHandlerResult]:
            handler = build_submit_deposit_handler(session)
            return await handler.validate_and_store_initial_tx(command)

        return await submission_executor_fn(handle_submit_deposit_fn)

    return execute_fn
