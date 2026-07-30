from typing import Protocol

from ...entities import Transaction


class TransactionCommandRepository(Protocol):
    async def add(self, transaction: Transaction) -> None: ...
