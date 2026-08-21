from aiokafka import AIOKafkaProducer

from app.config import KafkaSettings

from ...shared.dependencies import build_aiokafka_producer
from .dlq_publisher import DlqPublisher


def build_dlq_publisher(
    settings: KafkaSettings,
    *,
    producer: AIOKafkaProducer | None = None,
) -> DlqPublisher:
    return DlqPublisher(
        producer if producer is not None else build_aiokafka_producer(settings),
        settings.dlq_topic,
    )
