from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BalanceItemResponse(BaseModel):
    asset: str
    available: str


class BalanceListResponse(BaseModel):
    items: list[BalanceItemResponse] = Field(default_factory=list)


class TransactionItemResponse(BaseModel):
    id: UUID
    type: str
    status: str
    created_at: datetime


class TransactionListResponse(BaseModel):
    total_items: int
    items: list[TransactionItemResponse] = Field(default_factory=list)
