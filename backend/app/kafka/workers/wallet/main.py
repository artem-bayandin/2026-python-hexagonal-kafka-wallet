import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import load_worker_runtime

from ...runtime import (
    ReadinessError,
    check_kafka_topics,
    check_postgres,
    check_schema_revision,
    check_worker_consumer_group,
    configure_process_logging,
    register_shutdown_handlers,
)
from ...shared.dependencies import build_aiokafka_consumer
from ...worker import build_worker_execution_registry
from ...topics.wallet.factory_consumer import build_wallet_worker_consumer
from ...topics.wallet.factory_publisher import build_kafka_command_publisher
from ...topics.dlq.factory_publisher import build_dlq_publisher

logger = logging.getLogger(__name__)


async def run_wallet_worker() -> int:
    runtime = load_worker_runtime()
    configure_process_logging(runtime.settings.log_level)

    engine: AsyncEngine = create_async_engine(runtime.settings.database_url)
    shutdown_event = asyncio.Event()
    register_shutdown_handlers(shutdown_event)
    _consumer = build_aiokafka_consumer(
        runtime.kafka,
        runtime.worker,
        runtime.kafka.command_topic,
        runtime.kafka.worker_group_id,
    )
    _kafka_publisher = build_kafka_command_publisher(runtime.kafka)
    _dlq_publisher = build_dlq_publisher(runtime.kafka)
    worker = build_wallet_worker_consumer(
        consumer=_consumer,
        kafka_publisher=_kafka_publisher,
        dlq_publisher=_dlq_publisher,
        runtime=runtime,
        engine=engine,
        shutdown_event=shutdown_event,
        execution_registry=build_worker_execution_registry(engine),
    )
    started = False

    try:
        await check_postgres(engine)
        await check_schema_revision(engine)
        await worker.start()
        started = True
        await check_kafka_topics(
            worker.kafka_publisher.producer,
            runtime.kafka,
            include_dlq=True,
        )
        await check_worker_consumer_group(worker.consumer, runtime.kafka)
        logger.info(
            "worker ready",
            extra={
                "command_topic": runtime.kafka.command_topic,
                "dlq_topic": runtime.kafka.dlq_topic,
                "group_id": runtime.kafka.worker_group_id,
            },
        )
        await worker.run()
    except ReadinessError:
        logger.exception("worker readiness failed")
        return 1
    except Exception:
        logger.exception("worker failed")
        return 1
    finally:
        if started:
            await worker.stop()
        await engine.dispose()

    logger.info("worker stopped")
    return 0


async def main() -> int:
    return await run_wallet_worker()
