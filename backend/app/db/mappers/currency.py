from app.domain import CurrencyCatalogItem

from ..models import CurrencyModel


def currency_to_catalog_item(model: CurrencyModel) -> CurrencyCatalogItem:
    return CurrencyCatalogItem(
        label=model.label,
        name=model.name,
        type=model.type,
        precision=model.precision,
    )
