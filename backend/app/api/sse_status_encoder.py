import base64
import json
from datetime import UTC, datetime
from uuid import UUID

from app.notifier import StatusCursor, TransactionStatusEvent


class SseStatusEncoder:
    @staticmethod
    def encode_status_event_id(event: TransactionStatusEvent) -> str:
        payload = json.dumps(
            {
                "updated_at": SseStatusEncoder._to_rfc3339(event.updated_at),
                "id": str(event.transaction_id),
            },
            separators=(",", ":"),
        )
        return base64.urlsafe_b64encode(payload.encode("utf-8")).rstrip(b"=").decode("ascii")

    @staticmethod
    def decode_status_event_id(value: str | None) -> StatusCursor | None:
        if value is None or value.strip() == "":
            return None
        try:
            padded = value + "=" * (-len(value) % 4)
            raw = base64.urlsafe_b64decode(padded.encode("ascii"))
            payload = json.loads(raw.decode("utf-8"))
            updated_at = datetime.fromisoformat(str(payload["updated_at"]).replace("Z", "+00:00"))
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            return StatusCursor(
                updated_at=updated_at.astimezone(UTC),
                transaction_id=UUID(str(payload["id"])),
            )
        except KeyError, TypeError, ValueError, json.JSONDecodeError:
            return None

    @staticmethod
    def format_status_sse_event(event: TransactionStatusEvent) -> str:
        event_id = SseStatusEncoder.encode_status_event_id(event)
        data = json.dumps(
            {
                "request_id": str(event.request_id),
                "status": event.status.value,
                "type": event.type,
                "error": event.error,
            },
            separators=(",", ":"),
        )
        return f"id: {event_id}\nevent: transaction_status\ndata: {data}\n\n"

    @staticmethod
    def _to_rfc3339(value: datetime) -> str:
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return aware.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
