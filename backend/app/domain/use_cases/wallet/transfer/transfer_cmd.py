from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransferCommand:
    recipient_email: str
    asset_label: str
    amount_str: str
