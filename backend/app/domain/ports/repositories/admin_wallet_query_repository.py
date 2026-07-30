from typing import Protocol

from ...read_models.balance_item import BalanceItem


class AdminWalletQueryRepository(Protocol):
    async def list_all_with_labels(self) -> list[BalanceItem]: ...
