from collections.abc import Awaitable, Callable

from fastapi import Request

from app.db import AsyncSession
from app.dependencies import build_submit_exchange_handler
from app.domain import ExchangeCommand, Result, SubmissionInterimHandlerResult, SubmissionResult

from ..current_user_provider import get_current_user_provider
from .submission import get_submission_executor_fn

ExchangeExecutor = Callable[[ExchangeCommand], Awaitable[Result[SubmissionResult]]]


def get_exchange_executor_fn(request: Request) -> ExchangeExecutor:
    submission_executor_fn = get_submission_executor_fn(request)

    async def execute_fn(command: ExchangeCommand) -> Result[SubmissionResult]:
        async def handle_submit_exchange_fn(
            session: AsyncSession,
        ) -> Result[SubmissionInterimHandlerResult]:
            handler = build_submit_exchange_handler(
                session,
                get_current_user_provider(),
            )
            return await handler.validate_and_store_initial_tx(command)

        return await submission_executor_fn(handle_submit_exchange_fn)

    return execute_fn


__all__ = ["ExchangeExecutor", "get_exchange_executor_fn"]
