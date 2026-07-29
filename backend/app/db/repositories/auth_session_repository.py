from uuid import UUID

from sqlalchemy import select

from app.domain import AuthSession, AuthSessionRepository

from ..mappers import auth_session_to_domain, auth_session_to_model
from ..models import AuthSessionModel
from ..session import AsyncSession


class AuthSessionRepositoryImpl(AuthSessionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, session: AuthSession) -> None:
        self.session.add(auth_session_to_model(session))

    async def get_by_jti(self, jti: UUID) -> AuthSession | None:
        stmt = select(AuthSessionModel).where(AuthSessionModel.jti == jti)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return auth_session_to_domain(model)
