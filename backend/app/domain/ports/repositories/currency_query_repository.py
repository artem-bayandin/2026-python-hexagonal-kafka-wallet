from typing import Protocol

from ...read_models import CurrencyCatalogItem


class CurrencyQueryRepository(Protocol):
    async def list_all_ordered_by_label(self) -> list[CurrencyCatalogItem]: ...
