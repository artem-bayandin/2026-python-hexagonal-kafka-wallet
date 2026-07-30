from typing import Protocol
from uuid import UUID

from ...read_models.pagination import PaginatedResult, PaginationParams
from ...read_models.transaction_list_item import TransactionListItem


class TransactionQueryRepository(Protocol):
    async def list_admin_page(
        self, params: PaginationParams
    ) -> PaginatedResult[TransactionListItem]: ...

    async def list_user_page(
        self, user_id: UUID, params: PaginationParams
    ) -> PaginatedResult[TransactionListItem]: ...
