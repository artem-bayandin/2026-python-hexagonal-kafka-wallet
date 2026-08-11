from decimal import Decimal

from app.domain import BalanceItem


def wallet_row_to_balance_item(
    label: str,
    amount: Decimal,
    locked: Decimal,
    precision: int,
) -> BalanceItem:
    return BalanceItem(asset=label, amount=amount, locked=locked, precision=precision)
