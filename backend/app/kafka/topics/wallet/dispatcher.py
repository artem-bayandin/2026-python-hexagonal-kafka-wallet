import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any
from uuid import UUID

from aiokafka.structs import ConsumerRecord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import WorkerSettings
from app.domain import (
    WALLET_TX_MSG_INVALID,
    WalletTxMessage,
    WalletTxType,
    ExecutionHandlerRegistry,
    PoisonExecutionError,
    TERMINAL_STATUSES,
    TransactionCommandRepository,
    TransactionItem,
    TransactionQueryRepository,
    TransactionStatus,
    WALLET_TX_MESSAGE_INVALID,
    SAFE_EXECUTION_FAILED,
    SAFE_HANDLER_NOT_ENABLED,
    SAFE_TRANSACTION_NOT_FOUND,
    SAFE_TYPE_MISMATCH,
)

from ...workers.visibility import await_submitted_visibility_delay
from ..dlq.dlq_context import build_dlq_context
from ..dlq.dlq_publisher import DlqPublisher
from .wallet_tx_msg_mapper import WalletTxMsgMapper

logger = logging.getLogger(__name__)


class DispatchAction(Enum):
    ACK = auto()
    DEFER = auto()


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    action: DispatchAction


class RecordDispatcher:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tx_query_repo_factory: Callable[[AsyncSession], TransactionQueryRepository],
        tx_command_repo_factory: Callable[[AsyncSession], TransactionCommandRepository],
        execution_registry: ExecutionHandlerRegistry,
        dlq_publisher: DlqPublisher,
        worker_settings: WorkerSettings,
    ) -> None:
        self._session_factory = session_factory
        self._tx_query_repo_factory = tx_query_repo_factory
        self._tx_command_repo_factory = tx_command_repo_factory
        self._execution_registry = execution_registry
        self._dlq_publisher = dlq_publisher
        self._worker_settings = worker_settings

    async def dispatch(self, record: ConsumerRecord[Any, Any]) -> DispatchOutcome:
        key = record.key.decode("utf-8") if record.key is not None else ""
        parsed = self._try_parse_record(record)
        if parsed is None:
            return await self._poison_unreadable(key)

        log_extra = {
            "request_id": str(parsed.request_id),
            "msg_tx_type": str(parsed.msg_tx_type),
            "partition": str(record.partition),
            "offset": str(record.offset),
        }
        logger.info("worker delivery received", extra=log_extra)

        observation_result_or_tx = await self._observe_transaction(key, parsed, log_extra)
        if isinstance(observation_result_or_tx, DispatchOutcome):
            return observation_result_or_tx

        claimed_or_locked = await self._claim_or_lock(parsed.request_id, observation_result_or_tx)
        if claimed_or_locked is None:
            logger.info("worker claim deferred", extra=log_extra)
            return DispatchOutcome(action=DispatchAction.DEFER)

        return await self._execute(key, parsed, claimed_or_locked, log_extra)

    def _try_parse_record(self, record: ConsumerRecord[Any, Any]) -> WalletTxMessage | None:
        if record.value is None:
            return None
        decode_result = WalletTxMsgMapper.from_json(record.value)
        if not decode_result.is_success or decode_result.data is None:
            return None
        return decode_result.data

    async def _get_by_request_id(self, request_id: UUID) -> TransactionItem | None:
        async with self._session_factory() as session:
            return await self._tx_query_repo_factory(session).get_by_request_id(request_id)

    async def _reload_after_visibility(self, request_id: UUID) -> TransactionItem | None:
        await await_submitted_visibility_delay(self._worker_settings)
        return await self._get_by_request_id(request_id)

    async def _observe_transaction(
        self,
        key: str,
        message: WalletTxMessage,
        log_extra: dict[str, str],
    ) -> TransactionItem | DispatchOutcome:
        request_id = message.request_id
        transaction = await self._get_by_request_id(request_id)
        if transaction is None:
            transaction = await self._reload_after_visibility(request_id)
            if transaction is None:
                await self._publish_poison_dlq(
                    key=key,
                    message=message,
                    request_id=str(request_id),
                    msg_tx_type=str(message.msg_tx_type),
                    failure_classification="transaction_not_found",
                    safe_error=SAFE_TRANSACTION_NOT_FOUND,
                    attempt_count=0,
                )
                return DispatchOutcome(action=DispatchAction.ACK)

        if transaction.type != str(message.msg_tx_type):
            await self._terminal_poison_failure(
                key=key,
                message=message,
                transaction=transaction,
                safe_error=SAFE_TYPE_MISMATCH,
                failure_classification="type_mismatch",
            )
            return DispatchOutcome(action=DispatchAction.ACK)

        if transaction.status in TERMINAL_STATUSES:
            logger.info("worker duplicate terminal skipped", extra=log_extra)
            return DispatchOutcome(action=DispatchAction.ACK)

        if transaction.status == TransactionStatus.SUBMITTED:
            transaction = await self._reload_after_visibility(request_id)
            if transaction is None:
                return DispatchOutcome(action=DispatchAction.DEFER)
            if transaction.status == TransactionStatus.SUBMITTED:
                logger.info("worker submitted race deferred", extra=log_extra)
                return DispatchOutcome(action=DispatchAction.DEFER)
            if transaction.status in TERMINAL_STATUSES:
                return DispatchOutcome(action=DispatchAction.ACK)

        return transaction

    async def _claim_or_lock(
        self,
        request_id: UUID,
        transaction: TransactionItem,
    ) -> TransactionItem | None:
        async with self._session_factory() as session, session.begin():
            tx_command_repo = self._tx_command_repo_factory(session)
            tx_query_repo = self._tx_query_repo_factory(session)
            if transaction.status == TransactionStatus.PENDING:
                in_progress = await tx_command_repo.update_for_execution(request_id)
                if in_progress is not None:
                    logger.info(
                        "worker claim succeeded",
                        extra={"request_id": str(request_id)},
                    )
                    return in_progress
                reloaded = await tx_query_repo.get_by_request_id(request_id)
                if reloaded is None or reloaded.status != TransactionStatus.IN_PROGRESS:
                    return None
                return reloaded
            if transaction.status == TransactionStatus.IN_PROGRESS:
                locked = await tx_command_repo.lock_by_request_id(request_id)
                if locked is None or locked.status != TransactionStatus.IN_PROGRESS:
                    return None
                return locked
        return None

    async def _execute(
        self,
        key: str,
        message: WalletTxMessage,
        claimed: TransactionItem,
        log_extra: dict[str, str],
    ) -> DispatchOutcome:
        try:
            await self._execute_claimed(claimed)
        except PoisonExecutionError as error:
            await self._terminal_poison_failure(
                key=key,
                message=message,
                transaction=claimed,
                safe_error=error.safe_error,
                failure_classification="execution_poison",
                attempt_count=1,
            )
        except Exception as error:
            await self._terminal_poison_failure(
                key=key,
                message=message,
                transaction=claimed,
                safe_error=SAFE_EXECUTION_FAILED,
                failure_classification=type(error).__name__,
                attempt_count=1,
            )
        else:
            logger.info("worker execution succeeded", extra=log_extra)
        return DispatchOutcome(action=DispatchAction.ACK)

    async def _execute_claimed(self, transaction: TransactionItem) -> None:
        try:
            tx_type = WalletTxType(transaction.type)
        except ValueError as error:
            raise PoisonExecutionError(SAFE_HANDLER_NOT_ENABLED) from error
        handler = self._execution_registry.get(tx_type)
        if handler is None:
            raise PoisonExecutionError(SAFE_HANDLER_NOT_ENABLED)
        await handler.execute(transaction)

    async def _poison_unreadable(self, key: str) -> DispatchOutcome:
        await self._publish_poison_dlq(
            key=key or "unknown",
            message=None,
            request_id=None,
            msg_tx_type=None,
            failure_classification=WALLET_TX_MSG_INVALID,
            safe_error=WALLET_TX_MESSAGE_INVALID,
            attempt_count=0,
        )
        return DispatchOutcome(action=DispatchAction.ACK)

    async def _terminal_poison_failure(
        self,
        *,
        key: str,
        message: WalletTxMessage,
        transaction: TransactionItem,
        safe_error: str,
        failure_classification: str,
        attempt_count: int = 0,
    ) -> None:
        await self._publish_poison_dlq(
            key=key,
            message=message,
            request_id=str(transaction.request_id),
            msg_tx_type=transaction.type,
            failure_classification=failure_classification,
            safe_error=safe_error,
            attempt_count=attempt_count,
        )
        async with self._session_factory() as session, session.begin():
            tx_command_repo = self._tx_command_repo_factory(session)
            if transaction.status == TransactionStatus.IN_PROGRESS:
                await tx_command_repo.complete_if_in_progress(transaction.request_id, safe_error)
            elif transaction.status == TransactionStatus.PENDING:
                await tx_command_repo.fail_if_pending(transaction.request_id, safe_error)
            elif transaction.status == TransactionStatus.SUBMITTED:
                await tx_command_repo.fail_if_submitted(transaction.request_id, safe_error)

    async def _publish_poison_dlq(
        self,
        *,
        key: str,
        message: WalletTxMessage | None,
        request_id: str | None,
        msg_tx_type: str | None,
        failure_classification: str,
        safe_error: str,
        attempt_count: int,
    ) -> None:
        context = build_dlq_context(
            request_id=request_id,
            msg_tx_type=msg_tx_type,
            failure_classification=failure_classification,
            safe_error=safe_error,
            attempt_count=attempt_count,
        )
        await self._dlq_publisher.publish_failure(key=key, message=message, context=context)
