from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WithdrawCommand:
    asset_label: str
    amount_str: str
