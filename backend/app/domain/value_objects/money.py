from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .asset import Asset


@dataclass(frozen=True, slots=True)
class Money:
    asset: Asset
    amount: Decimal

    @classmethod
    def parse(cls, asset_label: str, amount_str: str, precision: int) -> Money:
        asset = Asset.from_label(asset_label)
        try:
            amount = Decimal(amount_str)
        except InvalidOperation as error:
            raise ValueError("Invalid amount.") from error
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        exponent = amount.as_tuple().exponent
        if not isinstance(exponent, int):
            raise ValueError("Invalid amount.")
        scale = -exponent if exponent < 0 else 0
        if scale > precision:
            raise ValueError("Amount exceeds asset precision.")
        return cls(asset=asset, amount=amount)
