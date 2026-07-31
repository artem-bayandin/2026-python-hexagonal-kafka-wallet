from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...read_models import UserItem


class UserCommandRepository(Protocol):
    async def create_by_email_if_not_exists(
        self, email: str, user_id: UUID, created_at: datetime
    ) -> None: ...

    async def get_by_email_for_update(self, email: str) -> UserItem | None: ...
