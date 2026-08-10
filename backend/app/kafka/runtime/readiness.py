from pathlib import Path

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import KafkaSettings

_LOCAL_COMMAND_TOPIC_PARTITIONS = 3
_LOCAL_DLQ_TOPIC_PARTITIONS = 1


class ReadinessError(Exception):
    """A dependency required for process readiness is unavailable."""


def expected_alembic_revision() -> str:
    backend_root = Path(__file__).resolve().parents[3]
    script = ScriptDirectory.from_config(Config(str(backend_root / "alembic.ini")))
    head = script.get_current_head()
    if head is None:
        raise ReadinessError("No Alembic head revision is configured")
    return head


async def check_postgres(engine: AsyncEngine) -> None:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as error:
        raise ReadinessError("PostgreSQL is unavailable") from error


async def check_schema_revision(engine: AsyncEngine) -> None:
    expected = expected_alembic_revision()
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT version_num FROM alembic_version"))
            row = result.one_or_none()
    except Exception as error:
        raise ReadinessError("Could not read Alembic revision") from error
    if row is None:
        raise ReadinessError("Database schema is not migrated")
    actual = row[0]
    if actual != expected:
        raise ReadinessError(
            f"Database schema revision {actual!r} does not match expected {expected!r}"
        )


async def check_kafka_topics(
    producer: AIOKafkaProducer,
    kafka: KafkaSettings,
    *,
    command_topic_partitions: int = _LOCAL_COMMAND_TOPIC_PARTITIONS,
    include_dlq: bool = False,
    dlq_topic_partitions: int = _LOCAL_DLQ_TOPIC_PARTITIONS,
) -> None:
    topics: dict[str, int] = {kafka.command_topic: command_topic_partitions}
    if include_dlq:
        topics[kafka.dlq_topic] = dlq_topic_partitions
    try:
        for topic, expected_partitions in topics.items():
            partitions = await producer.partitions_for(topic)
            if partitions is None:
                raise ReadinessError(f"Kafka topic {topic!r} is missing")
            if len(partitions) != expected_partitions:
                raise ReadinessError(
                    f"Kafka topic {topic!r} has {len(partitions)} partitions; "
                    f"expected {expected_partitions}"
                )
    except ReadinessError:
        raise
    except Exception as error:
        raise ReadinessError("Kafka metadata is unavailable") from error


async def check_worker_consumer_group(consumer: AIOKafkaConsumer, kafka: KafkaSettings) -> None:
    try:
        topics = await consumer.topics()
    except Exception as error:
        raise ReadinessError("Kafka consumer group metadata is unavailable") from error
    if kafka.command_topic not in topics:
        raise ReadinessError(f"Kafka command topic {kafka.command_topic!r} is not visible")


__all__ = [
    "ReadinessError",
    "check_kafka_topics",
    "check_postgres",
    "check_schema_revision",
    "check_worker_consumer_group",
    "expected_alembic_revision",
]
