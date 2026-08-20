from aiokafka import AIOKafkaProducer

from app.config import KafkaSettings
from ...shared.dependencies import build_aiokafka_producer

from .wallet_publisher import KafkaWalletPublisher


def build_kafka_command_publisher(
    settings: KafkaSettings,
    *,
    producer: AIOKafkaProducer | None = None,
) -> KafkaWalletPublisher:
    return KafkaWalletPublisher(
        producer if producer is not None else build_aiokafka_producer(settings),
        settings.command_topic,
        max_retries=settings.producer_max_retries,
        retry_backoff_ms=settings.producer_retry_backoff_ms,
        retry_backoff_max_ms=settings.producer_retry_backoff_max_ms,
        delivery_timeout_ms=settings.producer_delivery_timeout_ms,
    )
