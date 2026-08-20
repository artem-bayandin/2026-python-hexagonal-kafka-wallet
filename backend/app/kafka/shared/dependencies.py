from typing import Any
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.config import KafkaSettings, WorkerSettings


def build_kafka_client_kwargs(settings: KafkaSettings) -> dict[str, Any]:
    """Connection options shared by Kafka producers and consumers."""
    options: dict[str, Any] = {
        "bootstrap_servers": settings.bootstrap_servers,
        "security_protocol": settings.security_protocol,
    }
    return options


def build_worker_consumer(
    kafka: KafkaSettings,
    worker: WorkerSettings,
) -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        kafka.command_topic,
        **build_kafka_client_kwargs(kafka),
        group_id=kafka.worker_group_id,
        enable_auto_commit=False,
        heartbeat_interval_ms=worker.heartbeat_interval_ms,
        session_timeout_ms=worker.session_timeout_ms,
        max_poll_interval_ms=worker.max_poll_interval_ms,
    )


def build_aiokafka_producer(settings: KafkaSettings) -> AIOKafkaProducer:
    return AIOKafkaProducer(
        **build_kafka_client_kwargs(settings),
        # Fixed Version 2 guarantees; intentionally not configurable.
        acks="all",
        enable_idempotence=True,
        request_timeout_ms=settings.producer_request_timeout_ms,
        retry_backoff_ms=settings.producer_retry_backoff_ms,
    )
