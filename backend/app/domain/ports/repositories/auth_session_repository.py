from typing import Protocol

from ...entities import AuthSession


class AuthSessionRepository(Protocol):
    async def add(self, session: AuthSession) -> None:
        ...
