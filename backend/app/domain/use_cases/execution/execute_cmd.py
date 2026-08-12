"""Shared worker execution contract and dispatch decisions.

| Situation | Decision |
| --- | --- |
| Terminal transaction observed | acknowledge and skip; no wallet mutation |
| Transaction still ``submitted`` | defer/safe-retry; never acknowledge as a duplicate |
| Guarded update affects zero rows | reload and observe; never force a transition |
| Retryable infrastructure failure | retry up to 3 local attempts with bounded backoff |
| Poison input | terminal failure path; no repeated attempts; no balance mutation |
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...messaging.command_envelope import CommandType
from ...read_models import TransactionItem


@dataclass(frozen=True, slots=True)
class ExecuteCommand:
    request_id: UUID
    command_type: CommandType


class ExecutionHandler(Protocol):
    async def execute(self, transaction: TransactionItem) -> None: ...


class ExecutionHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[CommandType, ExecutionHandler] = {}

    def register(self, command_type: CommandType, handler: ExecutionHandler) -> None:
        self._handlers[command_type] = handler

    def get(self, command_type: CommandType) -> ExecutionHandler | None:
        return self._handlers.get(command_type)


class RetryableExecutionError(Exception):
    """Infrastructure failure eligible for the bounded local retry loop."""


class PoisonExecutionError(Exception):
    """Deterministic failure that must not be retried."""

    def __init__(self, safe_error: str) -> None:
        super().__init__(safe_error)
        self.safe_error = safe_error


__all__ = [
    "ExecuteCommand",
    "ExecutionHandler",
    "ExecutionHandlerRegistry",
    "PoisonExecutionError",
    "RetryableExecutionError",
]
