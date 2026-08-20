import asyncio
import logging

from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.config import WorkerRuntime
from app.db import (
    AsyncSession,
    TransactionCommandRepositoryImpl,
    TransactionQueryRepositoryImpl,
    build_session_factory,
)
from app.domain import ExecutionHandlerRegistry

from ..shared.dependencies import build_worker_consumer
from ..dlq.dependencies import build_dlq_publisher
from ..dlq.dlq_publisher import DlqPublisher
from ..wallet.dependencies import build_kafka_command_publisher
from ..wallet.wallet_publisher import KafkaWalletPublisher

from .dispatcher import DispatchAction, RecordDispatcher


logger = logging.getLogger(__name__)


class WalletWorkerConsumer:
    def __init__(
        self,
        *,
        runtime: WorkerRuntime,
        engine: AsyncEngine,
        consumer: AIOKafkaConsumer,
        kafka_publisher: KafkaWalletPublisher,
        dlq_publisher: DlqPublisher,
        execution_registry: ExecutionHandlerRegistry,
        shutdown_event: asyncio.Event,
    ) -> None:
        self._runtime = runtime
        self._consumer = consumer
        self._kafka_publisher = kafka_publisher
        self._shutdown_event = shutdown_event
        session_factory: async_sessionmaker[AsyncSession] = build_session_factory(engine)
        self._dispatcher = RecordDispatcher(
            session_factory=session_factory,
            tx_query_repo_factory=TransactionQueryRepositoryImpl,
            tx_command_repo_factory=TransactionCommandRepositoryImpl,
            execution_registry=execution_registry,
            dlq_publisher=dlq_publisher,
            worker_settings=runtime.worker,
        )

    async def start(self) -> None:
        await self._consumer.start()
        await self._kafka_publisher.start()

    async def stop(self) -> None:
        await self._consumer.stop()
        await self._kafka_publisher.stop()

    @property
    def consumer(self) -> AIOKafkaConsumer:
        return self._consumer

    @property
    def kafka_publisher(self) -> KafkaWalletPublisher:
        return self._kafka_publisher

    async def run(self) -> None:
        while not self._shutdown_event.is_set():
            batch = await self._consumer.getmany(timeout_ms=self._runtime.worker.poll_timeout_ms)
            if not batch:
                continue
            for topic_partition, records in batch.items():
                for record in records:
                    if self._shutdown_event.is_set():
                        return
                    outcome = await self._dispatcher.dispatch(record)
                    if outcome.action == DispatchAction.ACK:
                        await self._consumer.commit(
                            {topic_partition: record.offset + 1},
                        )
                        logger.info(
                            "worker source ack",
                            extra={
                                "partition": str(record.partition),
                                "offset": str(record.offset),
                            },
                        )


def build_wallet_worker_consumer(
    *,
    runtime: WorkerRuntime,
    engine: AsyncEngine,
    shutdown_event: asyncio.Event,
    execution_registry: ExecutionHandlerRegistry | None = None,
) -> WalletWorkerConsumer:
    consumer = build_worker_consumer(runtime.kafka, runtime.worker)
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
