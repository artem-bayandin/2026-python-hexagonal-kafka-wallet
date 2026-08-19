from aiokafka import AIOKafkaProducer

from app.config import KafkaSettings

from .client_options import build_kafka_client_kwargs
from .producer import KafkaCommandPublisher


def build_aiokafka_producer(settings: KafkaSettings) -> AIOKafkaProducer:
    return AIOKafkaProducer(
        **build_kafka_client_kwargs(settings),
        # Fixed Version 2 guarantees; intentionally not configurable.
        acks="all",
        enable_idempotence=True,
        request_timeout_ms=settings.producer_request_timeout_ms,
        retry_backoff_ms=settings.producer_retry_backoff_ms,
    )


def build_kafka_command_publisher(
    settings: KafkaSettings,
    *,
    topic: str | None = None,
    producer: AIOKafkaProducer | None = None,
) -> KafkaCommandPublisher:
    return KafkaCommandPublisher(
        producer if producer is not None else build_aiokafka_producer(settings),
        topic or settings.command_topic,
        max_retries=settings.producer_max_retries,
        retry_backoff_ms=settings.producer_retry_backoff_ms,
        retry_backoff_max_ms=settings.producer_retry_backoff_max_ms,
        delivery_timeout_ms=settings.producer_delivery_timeout_ms,
    )


__all__ = [
    "build_aiokafka_producer",
    "build_kafka_command_publisher",
]
