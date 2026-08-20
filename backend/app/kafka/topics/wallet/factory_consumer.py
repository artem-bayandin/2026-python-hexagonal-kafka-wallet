import asyncio
from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.config import WorkerRuntime
from app.domain import ExecutionHandlerRegistry

from ..dlq.dlq_publisher import DlqPublisher
from .wallet_consumer import WalletWorkerConsumer


def build_wallet_consumer(
    *,
    consumer: AIOKafkaConsumer,
    dlq_publisher: DlqPublisher,
    runtime: WorkerRuntime,
    session_factory: async_sessionmaker[AsyncSession],
    shutdown_event: asyncio.Event,
    execution_registry: ExecutionHandlerRegistry,
) -> WalletWorkerConsumer:
    return WalletWorkerConsumer(
        runtime=runtime,
        session_factory=session_factory,
        consumer=consumer,
        dlq_publisher=dlq_publisher,
        execution_registry=execution_registry,
        shutdown_event=shutdown_event,
    )
