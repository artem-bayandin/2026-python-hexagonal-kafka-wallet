from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AdminDepositRequest(BaseModel):
    email: EmailStr
    asset: str = Field(max_length=6)
    amount: str


class SubmissionAcceptedResponse(BaseModel):
    request_id: UUID
