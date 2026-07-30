from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.engine import CursorResult

from app.domain import AuthSession, AuthSessionCommandRepository

from ..mappers import auth_session_to_model
from ..models import AuthSessionModel
from ..session import AsyncSession


class AuthSessionCommandRepositoryImpl(AuthSessionCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, session: AuthSession) -> None:
        self.session.add(auth_session_to_model(session))

    async def revoke(self, jti: UUID, revoked_at: datetime) -> bool:
        stmt = (
            update(AuthSessionModel)
            .where(
                AuthSessionModel.jti == jti,
                AuthSessionModel.revoked_at.is_(None),
                AuthSessionModel.expires_at > revoked_at,
            )
            .values(revoked_at=revoked_at)
        )
        result = cast(
            CursorResult[Any],
            await self.session.execute(stmt),
        )
        return result.rowcount == 1
