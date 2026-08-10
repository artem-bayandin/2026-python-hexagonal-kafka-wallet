import asyncio
import logging

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from aiokafka.structs import RecordMetadata

from app.domain import CommandEnvelope, CommandPublisher

from .envelope_codec import command_envelope_to_json

logger = logging.getLogger(__name__)

_ADMIN_KEY = "admin"


class PublishTimeoutError(TimeoutError):
    """A publish call exceeded the configured end-to-end delivery bound."""


def _key_class(key: str) -> str:
    return "admin" if key == _ADMIN_KEY else "user"


class KafkaCommandPublisher(CommandPublisher):
    """Bounded command publisher: acks=all and idempotence are configured on the
    underlying producer; retries and the end-to-end wait are bounded here."""

    def __init__(
        self,
        producer: AIOKafkaProducer,
        topic: str,
        *,
        max_retries: int,
        retry_backoff_ms: int,
        retry_backoff_max_ms: int,
        delivery_timeout_ms: int,
    ) -> None:
        self._producer = producer
        self._topic = topic
        self._max_retries = max_retries
        self._retry_backoff_ms = retry_backoff_ms
        self._retry_backoff_max_ms = retry_backoff_max_ms
        self._delivery_timeout_s = delivery_timeout_ms / 1000

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def publish(self, *, key: str, envelope: CommandEnvelope) -> None:
        if not key:
            raise ValueError("Kafka record key is required")
        value = command_envelope_to_json(envelope)
        key_bytes = key.encode("utf-8")
        log_context = {
            "topic": self._topic,
            "key_class": _key_class(key),
            "request_id": str(envelope.request_id),
            "command_type": str(envelope.type),
        }
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._delivery_timeout_s
        backoff_ms = self._retry_backoff_ms
        for attempt in range(self._max_retries + 1):
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise self._bounded_timeout(log_context)
            try:
                metadata = await asyncio.wait_for(
                    self._producer.send_and_wait(self._topic, key=key_bytes, value=value),
                    timeout=remaining,
                )
            except TimeoutError as error:
                raise self._bounded_timeout(log_context) from error
            except KafkaError as error:
                retriable = bool(getattr(error, "retriable", False))
                if not retriable or attempt == self._max_retries:
                    logger.error(
                        "kafka publish failed definitively",
                        extra={**log_context, "error_type": type(error).__name__},
                    )
                    raise
                logger.warning(
                    "kafka publish failed, retrying",
                    extra={
                        **log_context,
                        "error_type": type(error).__name__,
                        "attempt": attempt + 1,
                        "backoff_ms": backoff_ms,
                    },
                )
                await asyncio.sleep(min(backoff_ms / 1000, max(deadline - loop.time(), 0)))
                backoff_ms = min(backoff_ms * 2, self._retry_backoff_max_ms)
            else:
                self._log_success(metadata, log_context)
                return
        raise self._bounded_timeout(log_context)

    def _bounded_timeout(self, log_context: dict[str, str]) -> PublishTimeoutError:
        logger.error(
            "kafka publish exceeded delivery bound",
            extra={**log_context, "delivery_timeout_s": str(self._delivery_timeout_s)},
        )
        return PublishTimeoutError(
            f"Publish to {self._topic} exceeded the delivery timeout "
            f"of {self._delivery_timeout_s:.3f}s"
        )

    def _log_success(self, metadata: RecordMetadata, log_context: dict[str, str]) -> None:
        logger.info(
            "kafka publish acknowledged",
            extra={
                **log_context,
                "partition": str(metadata.partition),
                "offset": str(metadata.offset),
            },
        )
