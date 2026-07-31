from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TransactionItem:
    id: UUID
    type: str
    source_wallet_id: UUID | None
    source_amount: Decimal
    dest_wallet_id: UUID | None
    dest_amount: Decimal
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TransactionListItem:
    id: UUID
    type: str
    status: str
    created_at: datetime
    amount: Decimal
    source_asset: str | None
    dest_asset: str | None
    source_precision: int | None
    dest_precision: int | None
    direction: Literal["IN", "OUT"] | None = None


@dataclass(frozen=True, slots=True)
class TransactionListRow:
    id: UUID
    type: str
    status: str
    created_at: datetime
    amount: Decimal
    source_asset: str | None
    dest_asset: str | None
    source_precision: int | None
    dest_precision: int | None
    source_user_id: UUID | None
    dest_user_id: UUID | None


def transaction_list_row_to_item(
    row: TransactionListRow,
    *,
    viewer_user_id: UUID | None,
) -> TransactionListItem:
    direction: Literal["IN", "OUT"] | None = None
    if viewer_user_id is not None and row.type == "transfer":
        if row.source_user_id == viewer_user_id:
            direction = "OUT"
        elif row.dest_user_id == viewer_user_id:
            direction = "IN"

    return TransactionListItem(
        id=row.id,
        type=row.type,
        status=row.status,
        created_at=row.created_at,
        amount=row.amount,
        source_asset=row.source_asset,
        dest_asset=row.dest_asset,
        source_precision=row.source_precision,
        dest_precision=row.dest_precision,
        direction=direction,
    )
