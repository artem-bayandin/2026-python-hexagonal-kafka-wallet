from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...read_models import AuthSessionItem


class AuthSessionCommandRepository(Protocol):
    async def add(self, session: AuthSessionItem) -> None: ...

    async def revoke(self, jti: UUID, revoked_at: datetime) -> bool: ...
