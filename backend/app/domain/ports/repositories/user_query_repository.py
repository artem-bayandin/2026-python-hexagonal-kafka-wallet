from typing import Protocol
from uuid import UUID

from ...read_models import UserReferenceItem, UserItem


class UserQueryRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> UserItem | None: ...

    async def get_by_email(self, email: str) -> UserItem | None: ...

    async def get_all_ordered_by_email(self) -> list[UserReferenceItem]: ...
