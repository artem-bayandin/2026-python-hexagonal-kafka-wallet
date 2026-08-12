import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.domain import CommandEnvelope
from app.kafka.messaging import KafkaCommandPublisher


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DlqContext:
    request_id: str | None
    command_type: str | None
    failure_classification: str
    safe_error: str
    attempt_count: int
    failed_at: datetime


class DlqPublisher:
    def __init__(self, publisher: KafkaCommandPublisher, *, topic: str) -> None:
        self._publisher = publisher
        self._topic = topic

    async def publish_failure(
        self,
        *,
        key: str,
        envelope: CommandEnvelope | None,
        context: DlqContext,
    ) -> None:
        payload = dlq_payload_to_json(key=key, envelope=envelope, context=context)
        log_extra = {
            "request_id": context.request_id,
            "command_type": context.command_type,
            "failure_classification": context.failure_classification,
            "attempt_count": str(context.attempt_count),
        }
        logger.info("dlq publish attempt", extra=log_extra)
        try:
            await self._publisher.producer.send_and_wait(
                self._topic,
                key=key.encode("utf-8"),
                value=payload,
            )
        except Exception:
            logger.exception(
                "dlq publish failed; source record must remain unacknowledged",
                extra=log_extra,
                exc_info=True,
            )
            raise
        logger.info("dlq publish acknowledged", extra=log_extra)


def dlq_payload_to_json(
    *,
    key: str,
    envelope: CommandEnvelope | None,
    context: DlqContext,
) -> bytes:
    payload: dict[str, Any] = {
        "original_key": key,
        "failure_classification": context.failure_classification,
        "safe_error": context.safe_error,
        "attempt_count": context.attempt_count,
        "failed_at": context.failed_at.isoformat(),
    }
    if envelope is not None:
        payload["request_id"] = str(envelope.request_id)
        payload["type"] = str(envelope.type)
        payload["submitted_at"] = envelope.submitted_at.isoformat()
    elif context.request_id is not None:
        payload["request_id"] = context.request_id
    if context.command_type is not None:
        payload["type"] = context.command_type
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def build_dlq_context(
    *,
    request_id: str | None,
    command_type: str | None,
    failure_classification: str,
    safe_error: str,
    attempt_count: int,
) -> DlqContext:
    return DlqContext(
        request_id=request_id,
        command_type=command_type,
        failure_classification=failure_classification,
        safe_error=safe_error,
        attempt_count=attempt_count,
        failed_at=datetime.now(UTC),
    )


def dlq_failed_at() -> datetime:
    return datetime.now(UTC)
