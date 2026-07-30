from decimal import Decimal

from app.domain import BalanceItem


def admin_wallet_row_to_balance_item(label: str, amount: Decimal) -> BalanceItem:
    return BalanceItem(asset=label, available=amount)
