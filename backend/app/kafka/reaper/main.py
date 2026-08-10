import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import load_reaper_runtime
from app.db import build_session_factory
from app.kafka.messaging import build_kafka_command_publisher
from app.kafka.runtime import (
    ReadinessError,
    check_kafka_topics,
    check_postgres,
    check_schema_revision,
    configure_process_logging,
    register_shutdown_handlers,
)

logger = logging.getLogger(__name__)


async def run_reaper() -> int:
    runtime = load_reaper_runtime()
    configure_process_logging(runtime.settings.log_level)

    engine: AsyncEngine = create_async_engine(runtime.settings.database_url)
    _session_factory = build_session_factory(engine)
    publisher = build_kafka_command_publisher(runtime.kafka)
    shutdown_event = asyncio.Event()
    register_shutdown_handlers(shutdown_event)
    publisher_started = False

    try:
        await check_postgres(engine)
        await check_schema_revision(engine)
        await publisher.start()
        publisher_started = True
        await check_kafka_topics(publisher.producer, runtime.kafka)
        logger.info(
            "reaper ready",
            extra={
                "command_topic": runtime.kafka.command_topic,
                "interval_seconds": runtime.reaper.interval_seconds,
            },
        )

        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=runtime.reaper.interval_seconds,
                )
            except TimeoutError:
                logger.debug(
                    "reaper idle tick",
                    extra={"interval_seconds": runtime.reaper.interval_seconds},
                )
    except ReadinessError:
        logger.exception("reaper readiness failed")
        return 1
    except Exception:
        logger.exception("reaper failed")
        return 1
    finally:
        if publisher_started:
            await publisher.stop()
        await engine.dispose()

    logger.info("reaper stopped")
    return 0


async def main() -> int:
    return await run_reaper()


__all__ = ["main", "run_reaper"]
