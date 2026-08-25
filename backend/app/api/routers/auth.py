from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.domain import LogoutCommand, RequestOtpCommand, VerifyOtpCommand

from ..dependencies import bind_current_user
from ..executors import (
    LogoutExecutorFn,
    RequestOtpExecutorFn,
    VerifyOtpExecutorFn,
    get_logout_executor_fn,
    get_request_otp_executor_fn,
    get_verify_otp_executor_fn,
)
from ..result_mapping import unwrap_domain_result
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
    response_model_exclude_none=True,
)
async def request_otp(
    payload: RequestOtpRequest,
    executor_fn: Annotated[RequestOtpExecutorFn, Depends(get_request_otp_executor_fn)],
) -> RequestOtpResponse:
    result = await executor_fn(RequestOtpCommand(email=str(payload.email)))
    data = unwrap_domain_result(result)
    assert data is not None
    return RequestOtpResponse(
        expires_at=data.expires_at,
        otp=data.demo_otp,
    )


@router.post(
    "/otp/verify",
    status_code=status.HTTP_200_OK,
)
async def verify_otp(
    payload: VerifyOtpRequest,
    executor_fn: Annotated[VerifyOtpExecutorFn, Depends(get_verify_otp_executor_fn)],
) -> VerifyOtpResponse:
    result = await executor_fn(VerifyOtpCommand(email=str(payload.email), otp=payload.otp))
    data = unwrap_domain_result(result)
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
    executor_fn: Annotated[LogoutExecutorFn, Depends(get_logout_executor_fn)],
) -> Response:
    result = await executor_fn(LogoutCommand())
    unwrap_domain_result(result)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
