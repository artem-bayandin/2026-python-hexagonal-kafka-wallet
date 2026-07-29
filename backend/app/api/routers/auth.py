from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.dependencies import execute_request_otp, execute_verify_otp
from app.domain import LogoutCommand, RequestOtpCommand, VerifyOtpCommand

from ..dependencies import (
    LogoutExecutor,
    bind_current_user,
    get_logout_executor,
)
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


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(bind_current_user)],
)
async def logout(
    executor: Annotated[LogoutExecutor, Depends(get_logout_executor)],
) -> Response:
    result = await executor(LogoutCommand())
    unwrap_result(result)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
