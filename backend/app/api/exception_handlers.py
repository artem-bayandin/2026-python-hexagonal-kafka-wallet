from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .result_mapping import ApiResultError

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


async def handle_validation_error(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise error
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "Request validation failed.",
        {"errors": error.errors()},
    )


async def handle_api_result_error(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, ApiResultError):
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
