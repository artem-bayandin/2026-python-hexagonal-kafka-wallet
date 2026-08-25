from app.domain import CurrencyItem, CurrencyCatalogItem

from ..models import CurrencyModel


class CurrencyDbMapper:
    @staticmethod
    def to_catalog_item(model: CurrencyModel) -> CurrencyCatalogItem:
        return CurrencyCatalogItem(
            label=model.label,
            name=model.name,
            type=model.type,
            precision=model.precision,
        )

    @staticmethod
    def to_domain(model: CurrencyModel) -> CurrencyItem:
        return CurrencyItem(
            id=model.id,
            type=model.type,
            name=model.name,
            label=model.label,
            precision=model.precision,
        )
