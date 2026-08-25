import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import load_worker_runtime
from app.db import build_session_factory

from ...runtime import (
    ReadinessError,
    check_kafka_topics,
    check_postgres,
    check_schema_revision,
    check_worker_consumer_group,
    configure_process_logging,
    register_shutdown_handlers,
)
from ...shared.dependencies import build_aiokafka_consumer, build_aiokafka_producer
from ...topics.wallet.factory_consumer import build_wallet_consumer
from ...topics.dlq.factory_publisher import build_dlq_publisher
from .execution_registry import build_wallet_execution_registry

logger = logging.getLogger(__name__)


async def run_wallet_worker() -> int:
    runtime = load_worker_runtime()
    configure_process_logging(runtime.settings.log_level)

    engine = create_async_engine(runtime.settings.database_url)
    session_factory = build_session_factory(engine)
    shutdown_event = asyncio.Event()
    register_shutdown_handlers(shutdown_event)

    # first goes producer, then consumer
    # The producer moved because it is a shared client with two jobs:
    # DLQ publish and check_kafka_topics
    producer = build_aiokafka_producer(runtime.kafka)
    dlq_publisher = build_dlq_publisher(runtime.kafka, producer=producer)

    # current consumer is only used in WallerConsumer, so for now we may not need it here
    # consumer = build_aiokafka_consumer(
    #     runtime.kafka,
    #     runtime.worker,
    #     runtime.kafka.command_topic,
    #     runtime.kafka.worker_group_id,
    # )
    wallet_consumer = build_wallet_consumer(
        consumer=build_aiokafka_consumer(
            runtime.kafka,
            runtime.worker,
            runtime.kafka.command_topic,
            runtime.kafka.worker_group_id,
        ),
        dlq_publisher=dlq_publisher,
        runtime=runtime,
        session_factory=session_factory,
        shutdown_event=shutdown_event,
        execution_registry=build_wallet_execution_registry(session_factory),
    )

    producer_started = False
    started = False
    try:
        await check_postgres(engine)
        await check_schema_revision(engine)
        await producer.start()
        producer_started = True
        await wallet_consumer.start()  # consumer.start() only
        started = True
        await check_kafka_topics(producer, runtime.kafka, include_dlq=True)
        await check_worker_consumer_group(wallet_consumer.consumer, runtime.kafka)
        logger.info(
            "worker ready",
            extra={
                "command_topic": runtime.kafka.command_topic,
                "dlq_topic": runtime.kafka.dlq_topic,
                "group_id": runtime.kafka.worker_group_id,
            },
        )
        await wallet_consumer.run()
    except ReadinessError:
        logger.exception("worker readiness failed")
        return 1
    except Exception:
        logger.exception("worker failed")
        return 1
    finally:
        if started:
            await wallet_consumer.stop()
        if producer_started:
            await producer.stop()
        await engine.dispose()

    logger.info("worker stopped")
    return 0


async def main() -> int:
    return await run_wallet_worker()
