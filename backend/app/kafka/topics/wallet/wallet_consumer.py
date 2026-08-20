import asyncio
import logging
from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.config import WorkerRuntime
from app.db import TransactionCommandRepositoryImpl, TransactionQueryRepositoryImpl
from app.domain import ExecutionHandlerRegistry

from ..dlq.dlq_publisher import DlqPublisher
from .dispatcher import DispatchAction, RecordDispatcher


logger = logging.getLogger(__name__)


class WalletWorkerConsumer:
    def __init__(
        self,
        *,
        runtime: WorkerRuntime,
        session_factory: async_sessionmaker[AsyncSession],
        consumer: AIOKafkaConsumer,
        dlq_publisher: DlqPublisher,
        execution_registry: ExecutionHandlerRegistry,
        shutdown_event: asyncio.Event,
    ) -> None:
        self._runtime = runtime
        self._consumer = consumer
        self._shutdown_event = shutdown_event
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

    async def stop(self) -> None:
        await self._consumer.stop()

    @property
    def consumer(self) -> AIOKafkaConsumer:
        return self._consumer

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
