from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserItem:
    id: UUID
    email: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UserReferenceItem:
    user_id: UUID
    email: str
