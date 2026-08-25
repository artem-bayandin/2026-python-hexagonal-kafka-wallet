"""Shared worker execution contract and dispatch decisions.

| Situation | Decision |
| --- | --- |
| Terminal transaction observed | acknowledge and skip; no wallet mutation |
| Transaction still ``submitted`` | defer/safe-retry; never acknowledge as a duplicate |
| Guarded update affects zero rows | reload and observe; never force a transition |
| Retryable infrastructure failure | first attempt is terminal; no in-process retry loop |
| Poison input | terminal failure path; no repeated attempts; no balance mutation |
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...messaging import WalletTxType
from ...read_models import TransactionItem


@dataclass(frozen=True, slots=True)
class ExecuteCommand:
    request_id: UUID
    msg_tx_type: WalletTxType


class ExecutionHandler(Protocol):
    async def execute(self, transaction: TransactionItem) -> None: ...


class ExecutionHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[WalletTxType, ExecutionHandler] = {}

    def register(self, msg_tx_type: WalletTxType, handler: ExecutionHandler) -> None:
        self._handlers[msg_tx_type] = handler

    def get(self, msg_tx_type: WalletTxType) -> ExecutionHandler | None:
        return self._handlers.get(msg_tx_type)


class RetryableExecutionError(Exception):
    """Infrastructure failure that is not treated as deterministic poison input."""


class PoisonExecutionError(Exception):
    """Deterministic failure that must not be retried."""

    def __init__(self, safe_error: str) -> None:
        super().__init__(safe_error)
        self.safe_error = safe_error
