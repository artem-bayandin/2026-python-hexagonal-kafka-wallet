from typing import Protocol
from uuid import UUID

from ...read_models import PaginatedResult, PaginationParams, TransactionListRow


class TransactionQueryRepository(Protocol):
    async def get_all_transactions_page(
        self, params: PaginationParams
    ) -> PaginatedResult[TransactionListRow]: ...

    async def get_user_transactions_page(
        self, user_id: UUID, params: PaginationParams
    ) -> PaginatedResult[TransactionListRow]: ...
