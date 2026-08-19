from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExchangeCommand:
    source_asset_label: str
    destination_asset_label: str
    amount_str: str
