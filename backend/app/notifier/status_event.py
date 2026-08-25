from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain import TransactionStatus


@dataclass(frozen=True, slots=True)
class StatusCursor:
    """Transparent resume key (updated_at, id). Opaque encoding is an API concern."""

    updated_at: datetime
    transaction_id: UUID


@dataclass(frozen=True, slots=True)
class TransactionStatusEvent:
    request_id: UUID
    status: TransactionStatus
    type: str
    error: str | None
    updated_at: datetime
    transaction_id: UUID
