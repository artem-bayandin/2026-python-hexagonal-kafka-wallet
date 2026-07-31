from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID


class AdminWalletCommandRepository(Protocol):
    async def get_for_update(self, currency_id: UUID) -> None: ...

    async def credit(self, currency_id: UUID, amount: Decimal, now: datetime) -> bool: ...
