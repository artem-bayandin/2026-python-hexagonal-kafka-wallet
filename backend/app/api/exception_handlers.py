from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .result_mapping import DomainResultError

ERROR_RESPONSES: dict[str, tuple[int, str]] = {
    "OTP_INVALID": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP is invalid.",
    ),
    "OTP_EXPIRED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP has expired.",
    ),
    "OTP_LOCKED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP is locked.",
    ),
    "OTP_CONSUMED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP has already been used.",
    ),
    "OTP_SUPERSEDED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP has been superseded.",
    ),
    "AUTHENTICATION_FAILED": (
        status.HTTP_401_UNAUTHORIZED,
        "Authentication failed.",
    ),
    "ADMIN_ACCESS_DENIED": (
        status.HTTP_403_FORBIDDEN,
        "Admin access denied.",
    ),
    "USER_NOT_FOUND": (
        status.HTTP_404_NOT_FOUND,
        "User not found.",
    ),
    "UNSUPPORTED_ASSET": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The asset is not supported.",
    ),
    "SAME_ASSET": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The source and destination assets cannot be the same.",
    ),
    "TRANSFER_TO_SELF": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The transfer cannot be to the same user.",
    ),
    "INVALID_AMOUNT": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The amount is invalid.",
    ),
    "INVALID_PRECISION": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The amount precision is invalid.",
    ),
    "INSUFFICIENT_FUNDS": (
        status.HTTP_409_CONFLICT,
        "The available balance is insufficient for this operation.",
    ),
    "CREDIT_FAILED": (
        status.HTTP_409_CONFLICT,
        "The credit failed.",
    ),
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": details or {},
        },
    )


async def handle_api_validation_error(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise error
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "Request validation failed.",
        {"errors": error.errors()},
    )


async def handle_domain_result_error(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, DomainResultError):
        raise error
    mapped = ERROR_RESPONSES.get(error.error_code)
    if mapped is None:
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Internal server error.",
        )
    status_code, message = mapped
    return error_response(status_code, error.error_code, message)


async def handle_uncaught_exception(_: Request, __: Exception) -> JSONResponse:
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_ERROR",
        "Internal server error.",
    )
