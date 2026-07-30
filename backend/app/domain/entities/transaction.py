from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Transaction:
    id: UUID
    type: str
    source_wallet_id: UUID | None
    source_amount: Decimal
    dest_wallet_id: UUID | None
    dest_amount: Decimal
    status: str
    created_at: datetime
