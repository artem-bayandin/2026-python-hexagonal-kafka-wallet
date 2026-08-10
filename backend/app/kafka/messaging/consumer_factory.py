from aiokafka import AIOKafkaConsumer

from app.config import KafkaSettings, WorkerSettings

from .client_options import build_kafka_client_kwargs


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


__all__ = ["build_worker_consumer"]
