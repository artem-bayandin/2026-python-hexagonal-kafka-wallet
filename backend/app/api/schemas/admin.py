from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AdminDepositRequest(BaseModel):
    email: EmailStr
    asset: str = Field(max_length=6)
    amount: str


class AdminDepositResponse(BaseModel):
    id: UUID
    type: str = "DEPOSIT"
    status: str = "COMPLETED"
