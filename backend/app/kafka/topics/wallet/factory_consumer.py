import asyncio
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import WorkerRuntime
from app.domain import ExecutionHandlerRegistry

from ...shared.dependencies import build_aiokafka_consumer
from ..dlq.dependencies import build_dlq_publisher
from .factory_publisher import build_kafka_command_publisher
from .wallet_consumer import WalletWorkerConsumer


def build_wallet_worker_consumer(
    *,
    runtime: WorkerRuntime,
    engine: AsyncEngine,
    shutdown_event: asyncio.Event,
    execution_registry: ExecutionHandlerRegistry | None = None,
) -> WalletWorkerConsumer:
    consumer = build_aiokafka_consumer(runtime.kafka, runtime.worker)
    kafka_publisher = build_kafka_command_publisher(runtime.kafka)
    dlq_publisher = build_dlq_publisher(runtime.kafka)
    return WalletWorkerConsumer(
        runtime=runtime,
        engine=engine,
        consumer=consumer,
        kafka_publisher=kafka_publisher,
        dlq_publisher=dlq_publisher,
        execution_registry=execution_registry or ExecutionHandlerRegistry(),
        shutdown_event=shutdown_event,
    )
