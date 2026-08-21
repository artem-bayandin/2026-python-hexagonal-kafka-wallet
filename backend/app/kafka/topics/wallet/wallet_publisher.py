import asyncio
import logging
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from aiokafka.structs import RecordMetadata

from app.domain import WalletTxMessage, MessagePublisher

from .wallet_tx_msg_mapper import WalletTxMsgMapper

logger = logging.getLogger(__name__)

_ADMIN_KEY = "admin"


class PublishTimeoutError(TimeoutError):
    """A publish call exceeded the configured end-to-end delivery bound."""


def _key_class(key: str) -> str:
    return "admin" if key == _ADMIN_KEY else key


class KafkaWalletPublisher(MessagePublisher):
    """Bounded message publisher: acks=all and idempotence are configured on the
    underlying producer; the end-to-end wait is bounded here."""

    def __init__(
        self,
        producer: AIOKafkaProducer,
        topic: str,
        *,
        delivery_timeout_ms: int,
    ) -> None:
        self._producer = producer
        self._topic = topic
        self._delivery_timeout_s = delivery_timeout_ms / 1000

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    @property
    def producer(self) -> AIOKafkaProducer:
        return self._producer

    async def publish(self, *, key: str, message: WalletTxMessage) -> None:
        if not key:
            raise ValueError("Kafka record key is required")
        value = WalletTxMsgMapper.to_json(message)
        key_bytes = key.encode("utf-8")
        log_context = {
            "topic": self._topic,
            "key_class": _key_class(key),
            "request_id": str(message.request_id),
            "msg_tx_type": str(message.msg_tx_type),
        }
        try:
            metadata = await asyncio.wait_for(
                self._producer.send_and_wait(self._topic, key=key_bytes, value=value),
                timeout=self._delivery_timeout_s,
            )
        except TimeoutError as error:
            raise self._bounded_timeout(log_context) from error
        except KafkaError as error:
            logger.error(
                "kafka publish failed definitively",
                extra={**log_context, "error_type": type(error).__name__},
            )
            raise
        self._log_success(metadata, log_context)

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
