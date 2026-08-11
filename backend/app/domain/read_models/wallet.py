from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BalanceItem:
    asset: str
    amount: Decimal
    locked: Decimal
    precision: int


@dataclass(frozen=True, slots=True)
class UserWalletItem:
    id: UUID
    user_id: UUID
    currency_id: UUID
    amount: Decimal
    locked: Decimal
    updated_at: datetime
