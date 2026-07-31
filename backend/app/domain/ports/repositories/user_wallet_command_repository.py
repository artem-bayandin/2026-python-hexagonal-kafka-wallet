from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from ...read_models import UserWalletItem


class UserWalletCommandRepository(Protocol):
    async def get_or_create_for_update(
        self, user_id: UUID, currency_id: UUID, wallet_id: UUID, now: datetime
    ) -> UserWalletItem: ...

    async def lock_for_update_ordered(self, wallet_ids: Sequence[UUID]) -> list[UserWalletItem]: ...

    async def credit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> bool: ...

    async def debit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> bool: ...
