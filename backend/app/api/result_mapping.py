from typing import TypeVar, cast

from app.domain import Result

T = TypeVar("T")


class ApiResultError(Exception):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)

def unwrap_result(result: Result[T]) -> T:
    if result.is_success:
        return cast("T", result.data)
    assert result.error_code is not None
    raise ApiResultError(result.error_code)
