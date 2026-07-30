from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserWallet:
    id: UUID
    user_id: UUID
    currency_id: UUID
    amount: Decimal
    updated_at: datetime
