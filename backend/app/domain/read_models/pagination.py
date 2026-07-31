from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PaginationParams:
    page_number: int
    page_size: int


@dataclass(frozen=True, slots=True)
class PaginatedResult[T]:
    total_items: int
    items: list[T]
