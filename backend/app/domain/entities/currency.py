from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Currency:
    id: UUID
    type: str
    name: str
    label: str
    precision: int
