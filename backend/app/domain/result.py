from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    _data: T | None = None
    _error_code: str | None = None
    _reason: Exception | None = None

    def __post_init__(self) -> None:
        valid_success = self._error_code is None and self._reason is None
        valid_failure = (
            self._error_code is not None
            and bool(self._error_code)
            and self._data is None
        )
        if not (valid_success or valid_failure):
            raise ValueError("Invalid Result initialization.")

    @classmethod
    def success(cls, data: T | None = None) -> Result[T]:
        return cls(_data=data)

    @classmethod
    def failure(
        cls, error_code: str, reason: Exception | None = None
    ) -> Result[T]:
        return cls(_error_code=error_code, _reason=reason)

    @property
    def is_success(self) -> bool:
        return self._error_code is None

    @property
    def data(self) -> T | None:
        return self._data

    @property
    def error_code(self) -> str | None:
        return self._error_code

    @property
    def reason(self) -> Exception | None:
        return self._reason
