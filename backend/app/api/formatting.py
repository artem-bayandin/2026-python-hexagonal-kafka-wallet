from decimal import Decimal


def map_not_null_asset_label(
    source_asset: str | None,
    dest_asset: str | None,
) -> str:
    if source_asset is not None:
        return source_asset
    if dest_asset is not None:
        return dest_asset
    raise ValueError("Transaction list item has no source or destination asset.")


def map_not_null_asset_precision(
    source_asset: str | None,
    dest_asset: str | None,
    source_precision: int | None,
    dest_precision: int | None,
) -> int:
    if source_asset is not None:
        if source_precision is None:
            raise ValueError("Transaction list item is missing source asset precision.")
        return source_precision
    if dest_asset is not None:
        if dest_precision is None:
            raise ValueError("Transaction list item is missing destination asset precision.")
        return dest_precision
    raise ValueError("Transaction list item has no source or destination asset.")


def format_amount_with_precision(amount: Decimal, precision: int) -> str:
    quantize_exp = Decimal("1").scaleb(-precision)
    formatted = amount.quantize(quantize_exp)
    return f"{formatted:f}"
