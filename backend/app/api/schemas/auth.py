from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RequestOtpRequest(BaseModel):
    email: EmailStr


class RequestOtpResponse(BaseModel):
    expires_at: datetime
    otp: str | None = Field(default=None)
