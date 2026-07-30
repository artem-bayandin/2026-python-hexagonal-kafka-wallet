from typing import Protocol
from uuid import UUID

from ...entities import AuthSession


class AuthSessionQueryRepository(Protocol):
    async def get_by_jti(self, jti: UUID) -> AuthSession | None: ...
