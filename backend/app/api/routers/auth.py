from fastapi import APIRouter, Request, status

from app.dependencies import execute_request_otp, execute_verify_otp
from app.domain import RequestOtpCommand, VerifyOtpCommand

from ..result_mapping import unwrap_result
from ..schemas import (
    RequestOtpRequest,
    RequestOtpResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/otp/request",
    status_code=status.HTTP_201_CREATED,
    response_model=RequestOtpResponse,
    response_model_exclude_none=True,
)
async def request_otp(
    payload: RequestOtpRequest,
    request: Request,
) -> RequestOtpResponse:
    result = await execute_request_otp(
        request,
        RequestOtpCommand(email=str(payload.email)),
    )
    data = unwrap_result(result)
    assert data is not None
    return RequestOtpResponse(
        expires_at=data.expires_at,
        otp=data.demo_otp,
    )


@router.post(
    "/otp/verify",
    status_code=status.HTTP_200_OK,
    response_model=VerifyOtpResponse,
)
async def verify_otp(
    payload: VerifyOtpRequest,
    request: Request,
) -> VerifyOtpResponse:
    result = await execute_verify_otp(
        request,
        VerifyOtpCommand(email=str(payload.email), otp=payload.otp),
    )
    data = unwrap_result(result)
    assert data is not None
    return VerifyOtpResponse(
        access_token=data.access_token,
        token_type="bearer",
        expires_at=data.expires_at,
    )
