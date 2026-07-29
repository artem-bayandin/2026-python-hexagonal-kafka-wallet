from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RequestOtpRequest(BaseModel):
    email: EmailStr


class RequestOtpResponse(BaseModel):
    expires_at: datetime
    otp: str | None = Field(default=None)


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")


class VerifyOtpResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime
