from typing import Protocol

from ...read_models import BalanceItem


class AdminWalletQueryRepository(Protocol):
    async def get_admin_balances(self) -> list[BalanceItem]: ...
