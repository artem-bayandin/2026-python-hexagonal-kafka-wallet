import json
from typing import Any

from app.domain import WalletTxMessage

from .dlq_context import DlqContext


class DlqMapper:
    @staticmethod
    def dlq_payload_to_json(
        *,
        key: str,
        message: WalletTxMessage | None,
        context: DlqContext,
    ) -> bytes:
        payload: dict[str, Any] = {
            "original_key": key,
            "failure_classification": context.failure_classification,
            "safe_error": context.safe_error,
            "attempt_count": context.attempt_count,
            "failed_at": context.failed_at.isoformat(),
        }
        if message is not None:
            payload["request_id"] = str(message.request_id)
            payload["type"] = str(message.msg_tx_type)
            payload["submitted_at"] = message.submitted_at.isoformat()
        elif context.request_id is not None:
            payload["request_id"] = context.request_id
        if context.msg_tx_type is not None:
            payload["type"] = context.msg_tx_type
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")
