from fastapi import APIRouter, Request, status

from app.dependencies import execute_request_otp
from app.domain import RequestOtpCommand

from ..result_mapping import unwrap_result
from ..schemas import RequestOtpRequest, RequestOtpResponse

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
