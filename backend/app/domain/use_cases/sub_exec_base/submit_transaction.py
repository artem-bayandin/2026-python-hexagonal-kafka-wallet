from dataclasses import dataclass
from uuid import UUID

from ...messaging import WalletTxMessage
from ...safe_errors import SAFE_PUBLICATION_FAILED


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    request_id: UUID


@dataclass(frozen=True, slots=True)
class SubmissionInterimHandlerResult:
    request_id: UUID
    key: str
    message: WalletTxMessage


class PublicationError(Exception):
    """Definitive bounded publication failure with a safe client-facing message."""

    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


def publication_error_from_exception(exc: Exception) -> PublicationError:
    return PublicationError(SAFE_PUBLICATION_FAILED)
