from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TransactionListItem:
    id: UUID
    type: str
    status: str
    created_at: datetime
    amount: Decimal
    source_asset: str | None
    dest_asset: str | None
