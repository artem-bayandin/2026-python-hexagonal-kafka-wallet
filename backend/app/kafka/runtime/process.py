import asyncio
import logging
import signal
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from aiokafka import AIOKafkaProducer

from app.config import LogLevel

logger = logging.getLogger(__name__)


def configure_process_logging(level: LogLevel) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def register_shutdown_handlers(shutdown_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        if not shutdown_event.is_set():
            logger.info("shutdown requested")
            shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_shutdown)


async def run_until_shutdown(
    shutdown_event: asyncio.Event,
    tick: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    while not shutdown_event.is_set():
        await tick()


@asynccontextmanager
async def managed_kafka_producer(producer: AIOKafkaProducer) -> AsyncIterator[AIOKafkaProducer]:
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()
