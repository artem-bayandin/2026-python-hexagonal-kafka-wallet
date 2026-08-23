from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from ..status_event import StatusCursor, TransactionStatusEvent


class StatusNotifier(Protocol):
    def subscribe(
        self, user_id: UUID, after: StatusCursor | None
    ) -> AsyncIterator[TransactionStatusEvent]: ...
