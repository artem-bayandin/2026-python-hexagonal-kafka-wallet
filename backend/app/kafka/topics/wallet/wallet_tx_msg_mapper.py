import json
from typing import Any

from app.domain import WALLET_TX_MSG_INVALID, WalletTxMessage, Result


class WalletTxMsgMapper:
    @staticmethod
    def to_json(message: WalletTxMessage) -> bytes:
        payload = {
            "request_id": str(message.request_id),
            "type": str(message.msg_tx_type),
            "submitted_at": message.submitted_at.isoformat(),
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def from_json(data: bytes) -> Result[WalletTxMessage]:
        """Decode the compact wire shape; malformed input is a domain failure, not an exception."""
        try:
            raw: Any = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            return Result.failure(WALLET_TX_MSG_INVALID, error)
        if not isinstance(raw, dict):
            return Result.failure(WALLET_TX_MSG_INVALID)
        return WalletTxMessage.try_parse(
            request_id=raw.get("request_id"),
            msg_tx_type=raw.get("type"),
            submitted_at=raw.get("submitted_at"),
        )
