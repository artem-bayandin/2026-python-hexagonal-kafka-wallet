import logging
from collections.abc import Callable
from datetime import UTC, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...messaging import WalletTxMessage, WalletTxType
from ...ports import (
    ClockService,
    MessagePublisher,
    TransactionCommandRepository,
    TransactionQueryRepository,
)
from ...read_models import StaleSubmittedCandidate

logger = logging.getLogger(__name__)


class ReapStaleSubmittedHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tx_query_repo_factory: Callable[[AsyncSession], TransactionQueryRepository],
        tx_command_repo_factory: Callable[[AsyncSession], TransactionCommandRepository],
        message_publisher: MessagePublisher,
        clock_service: ClockService,
        stale_threshold_seconds: int,
        batch_size: int,
        admin_partition_key: str,
    ) -> None:
        self._session_factory = session_factory
        self._tx_query_repo_factory = tx_query_repo_factory
        self._tx_command_repo_factory = tx_command_repo_factory
        self._message_publisher = message_publisher
        self._clock_service = clock_service
        self._stale_threshold_seconds = stale_threshold_seconds
        self._batch_size = batch_size
        self._admin_partition_key = admin_partition_key

    async def reap(self) -> None:
        cutoff = self._clock_service.now() - timedelta(seconds=self._stale_threshold_seconds)
        async with self._session_factory() as session, session.begin():
            tx_query_repo = self._tx_query_repo_factory(session)
            stale_pending = await tx_query_repo.count_stale_pending(cutoff)
            stale_in_progress = await tx_query_repo.count_stale_in_progress(cutoff)
            candidates = await tx_query_repo.list_stale_submitted(cutoff, self._batch_size)

        logger.info(
            "reaper scan",
            extra={
                "candidate_count": str(len(candidates)),
                "cutoff": cutoff.isoformat(),
            },
        )
        if stale_pending > 0:
            logger.error(
                "reaper stale pending alert",
                extra={
                    "stale_pending_count": str(stale_pending),
                    "cutoff": cutoff.isoformat(),
                },
            )
        if stale_in_progress > 0:
            logger.error(
                "reaper stale in_progress alert",
                extra={
                    "stale_in_progress_count": str(stale_in_progress),
                    "cutoff": cutoff.isoformat(),
                },
            )

        for candidate in candidates:
            await self._republish(candidate)

    async def _republish(self, candidate: StaleSubmittedCandidate) -> None:
        log_extra = {"request_id": str(candidate.request_id), "type": candidate.type}
        reconstructed = self._reconstruct(candidate)
        if reconstructed is None:
            return
        key, message = reconstructed
        try:
            await self._message_publisher.publish(key=key, message=message)
        except Exception:
            logger.exception("reaper publish failed", extra=log_extra)
            return

        async with self._session_factory() as session, session.begin():
            tx_command_repo = self._tx_command_repo_factory(session)
            updated = await tx_command_repo.mark_pending_if_submitted(candidate.request_id)
        if updated == 0:
            logger.info("reaper post-ack guarded no-op", extra=log_extra)
        else:
            logger.info("reaper republished", extra=log_extra)

    def _reconstruct(
        self, candidate: StaleSubmittedCandidate
    ) -> tuple[str, WalletTxMessage] | None:
        log_extra = {"request_id": str(candidate.request_id), "type": candidate.type}
        try:
            msg_tx_type = WalletTxType(candidate.type)
        except ValueError:
            logger.error("reaper skipped unknown transaction type", extra=log_extra)
            return None

        key = self._partition_key(msg_tx_type, candidate.source_user_id)
        if key is None:
            logger.error("reaper skipped missing partition key", extra=log_extra)
            return None

        submitted_at = candidate.created_at
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=UTC)
        else:
            submitted_at = submitted_at.astimezone(UTC)

        return key, WalletTxMessage(
            request_id=candidate.request_id,
            msg_tx_type=msg_tx_type,
            submitted_at=submitted_at,
        )

    def _partition_key(self, msg_tx_type: WalletTxType, source_user_id: UUID | None) -> str | None:
        if msg_tx_type is WalletTxType.DEPOSIT:
            return self._admin_partition_key
        if source_user_id is None:
            return None
        return str(source_user_id)
