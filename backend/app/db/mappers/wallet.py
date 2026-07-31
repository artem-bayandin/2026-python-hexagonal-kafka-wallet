from decimal import Decimal

from app.domain import BalanceItem


def wallet_row_to_balance_item(label: str, amount: Decimal, precision: int) -> BalanceItem:
    return BalanceItem(asset=label, available=amount, precision=precision)
