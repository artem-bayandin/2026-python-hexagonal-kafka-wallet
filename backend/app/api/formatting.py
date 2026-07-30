from decimal import Decimal


def format_amount(
    amount: Decimal,
    asset: str,
    precision_by_label: dict[str, int],
) -> str:
    precision = precision_by_label[asset]
    quantize_exp = Decimal("1").scaleb(-precision)
    formatted = amount.quantize(quantize_exp)
    return f"{formatted:f}"
