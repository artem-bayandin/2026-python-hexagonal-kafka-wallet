from typing import Protocol

from ...read_models import TransactionItem


class TransactionCommandRepository(Protocol):
    async def add(self, transaction: TransactionItem) -> None: ...
