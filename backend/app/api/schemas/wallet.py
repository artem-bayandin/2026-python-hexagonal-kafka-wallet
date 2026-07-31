from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class BalanceItemResponse(BaseModel):
    asset: str
    available: str


class BalanceListResponse(BaseModel):
    items: list[BalanceItemResponse] = Field(default_factory=list)


class TransactionItemResponse(BaseModel):
    id: UUID
    type: str
    status: str
    source_asset: str | None = None
    dest_asset: str | None = None
    amount: str
    created_at: datetime
    direction: str | None = None


class TransactionListResponse(BaseModel):
    total_items: int
    items: list[TransactionItemResponse] = Field(default_factory=list)


class ExchangeRequest(BaseModel):
    source_asset: str = Field(max_length=6)
    destination_asset: str = Field(max_length=6)
    amount: str


class WithdrawRequest(BaseModel):
    asset: str = Field(max_length=6)
    amount: str


class TransferRequest(BaseModel):
    email: EmailStr
    asset: str = Field(max_length=6)
    amount: str


class WalletMutationResponse(BaseModel):
    id: UUID
    type: str
    status: str = "COMPLETED"
