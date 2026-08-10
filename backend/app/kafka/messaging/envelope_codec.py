import json
from typing import Any

from app.domain import COMMAND_ENVELOPE_INVALID, CommandEnvelope, Result


def command_envelope_to_json(envelope: CommandEnvelope) -> bytes:
    payload = {
        "request_id": str(envelope.request_id),
        "type": str(envelope.type),
        "submitted_at": envelope.submitted_at.isoformat(),
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def json_to_command_envelope(data: bytes) -> Result[CommandEnvelope]:
    """Decode the compact wire shape; malformed input is a domain failure, not an exception."""
    try:
        raw: Any = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return Result.failure(COMMAND_ENVELOPE_INVALID, error)
    if not isinstance(raw, dict):
        return Result.failure(COMMAND_ENVELOPE_INVALID)
    return CommandEnvelope.try_parse(
        request_id=raw.get("request_id"),
        command_type=raw.get("type"),
        submitted_at=raw.get("submitted_at"),
    )
