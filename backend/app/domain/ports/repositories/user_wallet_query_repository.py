from typing import Protocol
from uuid import UUID

from ...read_models import BalanceItem


class UserWalletQueryRepository(Protocol):
    async def get_user_balances(self, user_id: UUID) -> list[BalanceItem]: ...
