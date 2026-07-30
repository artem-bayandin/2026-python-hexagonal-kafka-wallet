from uuid import UUID

from pydantic import BaseModel, EmailStr


class CurrencyItemResponse(BaseModel):
    label: str
    name: str
    type: str
    precision: int


class UserReferenceItemResponse(BaseModel):
    user_id: UUID
    email: EmailStr
