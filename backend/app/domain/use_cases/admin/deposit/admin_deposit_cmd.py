from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdminDepositCommand:
    email: str
    asset_label: str
    amount_str: str
