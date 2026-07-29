from typing import Protocol
from uuid import UUID

from ...entities import AuthSession


class AuthSessionRepository(Protocol):
    async def add(self, session: AuthSession) -> None:
        ...

    async def get_by_jti(self, jti: UUID) -> AuthSession | None:
        ...
