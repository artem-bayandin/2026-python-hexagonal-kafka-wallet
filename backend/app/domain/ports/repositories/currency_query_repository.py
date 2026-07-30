from typing import Protocol

from ...entities.currency import Currency
from ...read_models import CurrencyCatalogItem


class CurrencyQueryRepository(Protocol):
    async def list_all_ordered_by_label(self) -> list[CurrencyCatalogItem]: ...

    async def get_by_label(self, label: str) -> Currency | None: ...
