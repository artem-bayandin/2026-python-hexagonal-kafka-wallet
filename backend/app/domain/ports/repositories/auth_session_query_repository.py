from typing import Protocol
from uuid import UUID

from ...read_models import AuthSessionItem


class AuthSessionQueryRepository(Protocol):
    async def get_by_jti(self, jti: UUID) -> AuthSessionItem | None: ...
