from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurrencyCatalogItem:
    label: str
    name: str
    type: str
    precision: int
