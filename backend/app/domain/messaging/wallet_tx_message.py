from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from ..error_codes import WALLET_TX_MSG_INVALID
from ..result import Result


class WalletTxType(StrEnum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    EXCHANGE = "exchange"
    TRANSFER = "transfer"


@dataclass(frozen=True, slots=True)
class WalletTxMessage:
    request_id: UUID
    msg_tx_type: WalletTxType
    submitted_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID):
            raise ValueError("request_id must be a UUID.")
        if not isinstance(self.msg_tx_type, WalletTxType):
            raise ValueError("type must be one of the four command types.")
        if self.submitted_at.tzinfo is None or self.submitted_at.utcoffset() != timedelta(0):
            raise ValueError("submitted_at must be timezone-aware UTC.")

    @classmethod
    def try_parse(
        cls,
        *,
        request_id: object,
        msg_tx_type: object,
        submitted_at: object,
    ) -> Result[WalletTxMessage]:
        """Parse tolerated wire input into a wallet tx msg; malformed input is a domain failure."""
        try:
            parsed_request_id = (
                request_id if isinstance(request_id, UUID) else UUID(str(request_id))
            )
            parsed_type = (
                msg_tx_type
                if isinstance(msg_tx_type, WalletTxType)
                else WalletTxType(str(msg_tx_type))
            )
            parsed_submitted_at = (
                submitted_at
                if isinstance(submitted_at, datetime)
                else datetime.fromisoformat(str(submitted_at))
            )
            return Result.success(
                cls(
                    request_id=parsed_request_id,
                    msg_tx_type=parsed_type,
                    submitted_at=parsed_submitted_at,
                )
            )
        except (ValueError, TypeError) as error:
            return Result.failure(WALLET_TX_MSG_INVALID, error)
