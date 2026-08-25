from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from .wallet import TransactionItemResponse


class AdminDepositRequest(BaseModel):
    email: EmailStr
    asset: str = Field(max_length=6)
    amount: str


class SubmissionAcceptedResponse(BaseModel):
    request_id: UUID


class AdminTransactionPollResponse(BaseModel):
    items: list[TransactionItemResponse] = Field(default_factory=list)
    next_cursor: str | None = None
