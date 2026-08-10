import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import load_worker_runtime
from app.db import build_session_factory
from app.kafka.messaging import build_kafka_command_publisher, build_worker_consumer
from app.kafka.runtime import (
    ReadinessError,
    check_kafka_topics,
    check_postgres,
    check_schema_revision,
    check_worker_consumer_group,
    configure_process_logging,
    register_shutdown_handlers,
)

logger = logging.getLogger(__name__)


async def run_worker() -> int:
    runtime = load_worker_runtime()
    configure_process_logging(runtime.settings.log_level)

    engine: AsyncEngine = create_async_engine(runtime.settings.database_url)
    _session_factory = build_session_factory(engine)
    consumer = build_worker_consumer(runtime.kafka, runtime.worker)
    dlq_publisher = build_kafka_command_publisher(runtime.kafka, topic=runtime.kafka.dlq_topic)
    shutdown_event = asyncio.Event()
    register_shutdown_handlers(shutdown_event)
    consumer_started = False
    publisher_started = False

    try:
        await check_postgres(engine)
        await check_schema_revision(engine)
        await consumer.start()
        consumer_started = True
        await dlq_publisher.start()
        publisher_started = True
        await check_kafka_topics(
            dlq_publisher.producer,
            runtime.kafka,
            include_dlq=True,
        )
        await check_worker_consumer_group(consumer, runtime.kafka)
        logger.info(
            "worker ready",
            extra={
                "command_topic": runtime.kafka.command_topic,
                "dlq_topic": runtime.kafka.dlq_topic,
                "group_id": runtime.kafka.worker_group_id,
            },
        )

        while not shutdown_event.is_set():
            await consumer.getmany(timeout_ms=runtime.worker.poll_timeout_ms)
    except ReadinessError:
        logger.exception("worker readiness failed")
        return 1
    except Exception:
        logger.exception("worker failed")
        return 1
    finally:
        if consumer_started:
            await consumer.stop()
        if publisher_started:
            await dlq_publisher.stop()
        await engine.dispose()

    logger.info("worker stopped")
    return 0


async def main() -> int:
    return await run_worker()


__all__ = ["main", "run_worker"]
