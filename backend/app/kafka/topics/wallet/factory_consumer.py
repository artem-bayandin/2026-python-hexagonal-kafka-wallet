import asyncio
from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import WorkerRuntime
from app.domain import ExecutionHandlerRegistry

from ..dlq.dlq_publisher import DlqPublisher
from .wallet_consumer import WalletWorkerConsumer
from .wallet_publisher import KafkaWalletPublisher


def build_wallet_worker_consumer(
    *,
    consumer: AIOKafkaConsumer,
    kafka_publisher: KafkaWalletPublisher,
    dlq_publisher: DlqPublisher,
    runtime: WorkerRuntime,
    engine: AsyncEngine,
    shutdown_event: asyncio.Event,
    execution_registry: ExecutionHandlerRegistry | None = None,
) -> WalletWorkerConsumer:
    return WalletWorkerConsumer(
        runtime=runtime,
        engine=engine,
        consumer=consumer,
        kafka_publisher=kafka_publisher,
        dlq_publisher=dlq_publisher,
        execution_registry=execution_registry or ExecutionHandlerRegistry(),
        shutdown_event=shutdown_event,
    )
