from typing import cast

from app.domain import Result


class DomainResultError(Exception):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


def unwrap_domain_result[T](result: Result[T]) -> T:
    if result.is_success:
        return cast("T", result.data)
    assert result.error_code is not None
    raise DomainResultError(result.error_code)
