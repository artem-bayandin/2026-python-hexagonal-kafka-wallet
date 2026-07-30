from typing import Protocol
from uuid import UUID

from ...read_models.balance_item import BalanceItem


class UserWalletQueryRepository(Protocol):
    async def list_balances_for_user(self, user_id: UUID) -> list[BalanceItem]: ...
