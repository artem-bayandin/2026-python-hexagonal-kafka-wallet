from app.domain import Currency, CurrencyCatalogItem

from ..models import CurrencyModel


def currency_to_catalog_item(model: CurrencyModel) -> CurrencyCatalogItem:
    return CurrencyCatalogItem(
        label=model.label,
        name=model.name,
        type=model.type,
        precision=model.precision,
    )


def currency_to_domain(model: CurrencyModel) -> Currency:
    return Currency(
        id=model.id,
        type=model.type,
        name=model.name,
        label=model.label,
        precision=model.precision,
    )
