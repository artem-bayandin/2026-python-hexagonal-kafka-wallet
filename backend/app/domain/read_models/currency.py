from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CurrencyItem:
    id: UUID
    type: str
    name: str
    label: str
    precision: int


@dataclass(frozen=True, slots=True)
class CurrencyCatalogItem:
    label: str
    name: str
    type: str
    precision: int
