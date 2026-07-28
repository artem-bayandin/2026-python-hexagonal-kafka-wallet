from datetime import datetime
from typing import Protocol


class ClockService(Protocol):
    def now(self) -> datetime:
        ...
