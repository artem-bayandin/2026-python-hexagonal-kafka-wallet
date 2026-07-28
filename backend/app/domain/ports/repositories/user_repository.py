from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...entities import User


class UserRepository(Protocol):
    async def ensure_by_email(
        self
        , email: str
        , user_id: UUID
        , created_at: datetime
    ) -> None:
        ...

    async def get_by_email_for_update(self, email: str) -> User:
        ...
