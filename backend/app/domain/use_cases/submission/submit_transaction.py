from dataclasses import dataclass
from uuid import UUID

from ...messaging.command_envelope import CommandEnvelope
from ...ports import CommandPublisher, TransactionCommandRepository
from ...result import Result
from ...safe_errors import SAFE_PUBLICATION_FAILED


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    request_id: UUID


@dataclass(frozen=True, slots=True)
class SubmissionPersistOutcome:
    request_id: UUID
    key: str
    envelope: CommandEnvelope


class PublicationError(Exception):
    """Definitive bounded publication failure with a safe client-facing message."""

    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


def publication_error_from_exception(exc: Exception) -> PublicationError:
    return PublicationError(SAFE_PUBLICATION_FAILED)


class SubmitTransactionHandler:
    def __init__(
        self,
        command_publisher: CommandPublisher,
        tx_command_repo: TransactionCommandRepository,
    ) -> None:
        self._command_publisher = command_publisher
        self._tx_command_repo = tx_command_repo

    async def finalize_after_persist(
        self, outcome: SubmissionPersistOutcome
    ) -> Result[SubmissionResult]:
        try:
            await self._command_publisher.publish(key=outcome.key, envelope=outcome.envelope)
        except Exception as exc:
            publication_error = publication_error_from_exception(exc)
            await self._tx_command_repo.fail_if_submitted(
                outcome.request_id,
                publication_error.safe_message,
            )
        else:
            await self._tx_command_repo.mark_pending_if_submitted(outcome.request_id)
        return Result.success(SubmissionResult(request_id=outcome.request_id))
