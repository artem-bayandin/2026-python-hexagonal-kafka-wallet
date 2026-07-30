from decimal import Decimal


def amount_precision_asset(
    source_asset: str | None,
    dest_asset: str | None,
) -> str:
    if source_asset is not None:
        return source_asset
    if dest_asset is not None:
        return dest_asset
    raise ValueError("Transaction list item has no source or destination asset.")


def format_amount(
    amount: Decimal,
    asset: str,
    precision_by_label: dict[str, int],
) -> str:
    precision = precision_by_label[asset]
    quantize_exp = Decimal("1").scaleb(-precision)
    formatted = amount.quantize(quantize_exp)
    return f"{formatted:f}"
