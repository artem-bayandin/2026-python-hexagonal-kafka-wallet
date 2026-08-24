from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import SystemClock
from app.config import KafkaSettings, ReaperSettings
from app.db import TransactionCommandRepositoryImpl, TransactionQueryRepositoryImpl
from app.domain import ClockService, MessagePublisher, ReapStaleSubmittedHandler


def build_reap_stale_submitted_handler(
    session_factory: async_sessionmaker[AsyncSession],
    message_publisher: MessagePublisher,
    *,
    reaper_settings: ReaperSettings,
    kafka_settings: KafkaSettings,
    clock: ClockService | None = None,
) -> ReapStaleSubmittedHandler:
    clock_service = clock if clock is not None else SystemClock()
    return ReapStaleSubmittedHandler(
        session_factory,
        TransactionQueryRepositoryImpl,
        TransactionCommandRepositoryImpl,
        message_publisher,
        clock_service,
        reaper_settings.stale_threshold_seconds,
        reaper_settings.batch_size,
        kafka_settings.admin_partition_key,
    )
