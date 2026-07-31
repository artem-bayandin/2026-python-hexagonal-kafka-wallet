from typing import Protocol

from ...read_models import CurrencyCatalogItem, CurrencyItem


class CurrencyQueryRepository(Protocol):
    async def get_all_ordered_by_label(self) -> list[CurrencyCatalogItem]: ...

    async def get_by_label(self, label: str) -> CurrencyItem | None: ...
