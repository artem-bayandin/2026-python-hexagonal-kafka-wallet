from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Asset:
    label: str

    @classmethod
    def from_label(cls, label: str) -> Asset:
        normalized = label.strip().upper()
        if normalized not in {"USD", "USDT"}:
            raise ValueError("Unsupported asset label.")
        return cls(label=normalized)
