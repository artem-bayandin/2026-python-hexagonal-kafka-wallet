from dataclasses import dataclass

from ...ports import CurrencyQueryRepository
from ...read_models import CurrencyCatalogItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class ListCurrenciesQuery:
    pass


class ListCurrenciesHandler:
    def __init__(self, currency_query_repo: CurrencyQueryRepository) -> None:
        self._currency_query_repo = currency_query_repo

    async def handle(self, _: ListCurrenciesQuery) -> Result[list[CurrencyCatalogItem]]:
        items = await self._currency_query_repo.list_all_ordered_by_label()
        return Result.success(items)
