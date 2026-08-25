from collections.abc import Awaitable, Callable

from fastapi import Request

from app.db import AsyncSession
from app.dependencies import build_submit_transfer_handler
from app.domain import Result, SubmissionInterimHandlerResult, SubmissionResult, TransferCommand

from ..current_user_provider import get_current_user_provider
from .submission import get_submission_executor_fn

TransferExecutorFn = Callable[[TransferCommand], Awaitable[Result[SubmissionResult]]]


def get_transfer_executor_fn(request: Request) -> TransferExecutorFn:
    submission_executor_fn = get_submission_executor_fn(request)

    async def execute_fn(command: TransferCommand) -> Result[SubmissionResult]:
        async def handle_submit_transfer_fn(
            session: AsyncSession,
        ) -> Result[SubmissionInterimHandlerResult]:
            handler = build_submit_transfer_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.validate_and_store_initial_tx(command)

        return await submission_executor_fn(handle_submit_transfer_fn)

    return execute_fn
