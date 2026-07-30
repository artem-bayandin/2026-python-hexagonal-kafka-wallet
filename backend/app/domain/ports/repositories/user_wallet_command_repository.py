from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from ...entities import UserWallet


class UserWalletCommandRepository(Protocol):
    async def get_or_create_for_update(
        self, user_id: UUID, currency_id: UUID, wallet_id: UUID, now: datetime
    ) -> UserWallet: ...

    async def credit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> None: ...
