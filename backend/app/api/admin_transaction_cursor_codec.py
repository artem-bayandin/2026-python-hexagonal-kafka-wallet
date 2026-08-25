import base64
import binascii
import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain import AdminTransactionCursor

_BASE64URL_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)


class AdminTransactionCursorCodec:
    @staticmethod
    def encode(cursor: AdminTransactionCursor) -> str:
        payload = json.dumps(
            {
                "updated_at": AdminTransactionCursorCodec._to_rfc3339(cursor.updated_at),
                "id": str(cursor.transaction_id),
            },
            separators=(",", ":"),
        )
        return base64.urlsafe_b64encode(payload.encode("utf-8")).rstrip(b"=").decode("ascii")

    @staticmethod
    def decode(value: str | None) -> AdminTransactionCursor | None:
        if value is None or value == "":
            return None
        if not _BASE64URL_PATTERN.fullmatch(value) or len(value) % 4 == 1:
            raise ValueError("Invalid admin transaction cursor.")

        try:
            padded = value + "=" * (-len(value) % 4)
            raw = base64.b64decode(padded, altchars=b"-_", validate=True)
            canonical_value = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
            if canonical_value != value:
                raise ValueError("Invalid admin transaction cursor.")
            payload = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=AdminTransactionCursorCodec._object_from_unique_pairs,
            )
            if not isinstance(payload, dict) or set(payload) != {"updated_at", "id"}:
                raise ValueError("Invalid admin transaction cursor.")

            updated_at_value = payload["updated_at"]
            transaction_id_value = payload["id"]
            if not isinstance(updated_at_value, str) or not isinstance(transaction_id_value, str):
                raise ValueError("Invalid admin transaction cursor.")
            if not _RFC3339_PATTERN.fullmatch(updated_at_value):
                raise ValueError("Invalid admin transaction cursor.")

            updated_at = datetime.fromisoformat(updated_at_value.replace("Z", "+00:00"))
            normalized_updated_at = updated_at.astimezone(UTC)
            transaction_id = UUID(transaction_id_value)
            if str(transaction_id) != transaction_id_value:
                raise ValueError("Invalid admin transaction cursor.")
        except (
            binascii.Error,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            OverflowError,
            ValueError,
        ) as error:
            raise ValueError("Invalid admin transaction cursor.") from error

        return AdminTransactionCursor(
            updated_at=normalized_updated_at,
            transaction_id=transaction_id,
        )

    @staticmethod
    def _object_from_unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in pairs:
            if key in payload:
                raise ValueError("Invalid admin transaction cursor.")
            payload[key] = value
        return payload

    @staticmethod
    def _to_rfc3339(value: datetime) -> str:
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return aware.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
