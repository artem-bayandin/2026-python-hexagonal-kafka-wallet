import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import load_reaper_runtime
from app.db import build_session_factory

from ...topics.wallet.factory_publisher import build_wallet_publisher
from ...runtime import (
    ReadinessError,
    check_kafka_topics,
    check_postgres,
    check_schema_revision,
    configure_process_logging,
    register_shutdown_handlers,
)
from .dependencies import build_reap_stale_submitted_handler

logger = logging.getLogger(__name__)


async def run_reaper() -> int:
    runtime = load_reaper_runtime()
    configure_process_logging(runtime.settings.log_level)

    engine: AsyncEngine = create_async_engine(runtime.settings.database_url)
    session_factory = build_session_factory(engine)
    wallet_producer = build_wallet_publisher(runtime.kafka)
    handler = build_reap_stale_submitted_handler(
        session_factory,
        wallet_producer,
        reaper_settings=runtime.reaper,
        kafka_settings=runtime.kafka,
    )
    shutdown_event = asyncio.Event()
    register_shutdown_handlers(shutdown_event)
    publisher_started = False

    try:
        await check_postgres(engine)
        await check_schema_revision(engine)
        await wallet_producer.start()
        publisher_started = True
        await check_kafka_topics(wallet_producer.producer, runtime.kafka)
        logger.info(
            "reaper ready",
            extra={
                "command_topic": runtime.kafka.command_topic,
                "interval_seconds": runtime.reaper.interval_seconds,
                "stale_threshold_seconds": runtime.reaper.stale_threshold_seconds,
                "batch_size": runtime.reaper.batch_size,
            },
        )

        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=runtime.reaper.interval_seconds,
                )
            except TimeoutError:
                try:
                    await handler.reap()
                except Exception:
                    logger.exception("reaper pass failed")
    except ReadinessError:
        logger.exception("reaper readiness failed")
        return 1
    except Exception:
        logger.exception("reaper failed")
        return 1
    finally:
        if publisher_started:
            await wallet_producer.stop()
        await engine.dispose()

    logger.info("reaper stopped")
    return 0


async def main() -> int:
    return await run_reaper()
