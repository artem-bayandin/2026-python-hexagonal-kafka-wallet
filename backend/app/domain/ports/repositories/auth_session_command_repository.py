from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...entities import AuthSession


class AuthSessionCommandRepository(Protocol):
    async def add(self, session: AuthSession) -> None: ...

    async def revoke(self, jti: UUID, revoked_at: datetime) -> bool: ...
