from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class DlqContext:
    request_id: str | None
    msg_tx_type: str | None
    failure_classification: str
    safe_error: str
    attempt_count: int
    failed_at: datetime


def build_dlq_context(
    *,
    request_id: str | None,
    msg_tx_type: str | None,
    failure_classification: str,
    safe_error: str,
    attempt_count: int,
) -> DlqContext:
    return DlqContext(
        request_id=request_id,
        msg_tx_type=msg_tx_type,
        failure_classification=failure_classification,
        safe_error=safe_error,
        attempt_count=attempt_count,
        failed_at=datetime.now(UTC),
    )
