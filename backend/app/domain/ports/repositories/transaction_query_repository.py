from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...read_models import (
    AdminTransactionCursor,
    PaginatedResult,
    PaginationParams,
    StaleSubmittedCandidate,
    TransactionItem,
    TransactionListRow,
)


class TransactionQueryRepository(Protocol):
    async def list_all_transactions_after(
        self,
        after: AdminTransactionCursor | None,
        limit: int,
    ) -> list[TransactionListRow]: ...

    async def get_user_transactions_page(
        self, user_id: UUID, params: PaginationParams
    ) -> PaginatedResult[TransactionListRow]: ...

    async def get_by_request_id(self, request_id: UUID) -> TransactionItem | None: ...

    async def list_stale_submitted(
        self, cutoff: datetime, batch_size: int
    ) -> list[StaleSubmittedCandidate]: ...

    async def count_stale_pending(self, cutoff: datetime) -> int: ...

    async def count_stale_in_progress(self, cutoff: datetime) -> int: ...
