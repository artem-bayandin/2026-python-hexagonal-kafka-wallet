from typing import Protocol
from uuid import UUID

from ..status_event import StatusCursor, TransactionStatusEvent


class StatusEventRepository(Protocol):
    async def list_status_events_after(
        self, user_id: UUID, after: StatusCursor | None, limit: int
    ) -> list[TransactionStatusEvent]: ...

    async def get_status_high_water(self, user_id: UUID) -> StatusCursor | None: ...
