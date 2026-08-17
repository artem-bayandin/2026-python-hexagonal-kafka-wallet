from collections.abc import Awaitable, Callable

from fastapi import Request

from app.db import AsyncSession, TransactionCommandRepositoryImpl
from app.dependencies import build_command_publisher
from app.domain import (
    Result,
    SubmissionInterimHandlerResult,
    SubmissionResult,
    publication_error_from_exception,
)

from ..db_session import write_session

SubmissionInterimHandlerFn = Callable[
    [AsyncSession], Awaitable[Result[SubmissionInterimHandlerResult]]
]
SubmissionExecutorFn = Callable[[SubmissionInterimHandlerFn], Awaitable[Result[SubmissionResult]]]


def get_submission_executor_fn(request: Request) -> SubmissionExecutorFn:
    command_publisher = build_command_publisher(request.app.state.kafka_settings)  # object

    async def execute_fn(
        handle_initial_tx_creation_fn: SubmissionInterimHandlerFn,
    ) -> Result[SubmissionResult]:
        async with write_session(request) as session:
            handler_result = await handle_initial_tx_creation_fn(session)
            if not handler_result.is_success:
                return Result.failure(
                    handler_result.error_code or "INTERNAL_ERROR",
                    handler_result.reason,
                )
            outcome = handler_result.data
            if outcome is None:
                return Result.failure("INTERNAL_ERROR")

        try:
            await command_publisher.publish(key=outcome.key, envelope=outcome.envelope)
        except Exception as exc:
            publication_error = publication_error_from_exception(exc)
            async with write_session(request) as session:
                tx_command_repo = TransactionCommandRepositoryImpl(session)
                await tx_command_repo.fail_if_submitted(
                    outcome.request_id,
                    publication_error.safe_message,
                )
        else:
            async with write_session(request) as session:
                tx_command_repo = TransactionCommandRepositoryImpl(session)
                await tx_command_repo.mark_pending_if_submitted(outcome.request_id)

        return Result.success(SubmissionResult(request_id=outcome.request_id))

    return execute_fn


__all__ = ["SubmissionExecutorFn", "SubmissionInterimHandlerFn", "get_submission_executor_fn"]
