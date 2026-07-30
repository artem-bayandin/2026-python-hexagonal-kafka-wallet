from typing import Protocol
from uuid import UUID

from ...entities import User
from ...read_models import UserReferenceItem


class UserQueryRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def list_all_ordered_by_email(self) -> list[UserReferenceItem]: ...
