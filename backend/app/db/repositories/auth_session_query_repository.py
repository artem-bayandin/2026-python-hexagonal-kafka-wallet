from uuid import UUID

from sqlalchemy import select

from app.domain import AuthSessionItem, AuthSessionQueryRepository

from ..mappers import auth_session_to_domain
from ..models import AuthSessionModel
from ..session import AsyncSession


class AuthSessionQueryRepositoryImpl(AuthSessionQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_jti(self, jti: UUID) -> AuthSessionItem | None:
        stmt = select(AuthSessionModel).where(AuthSessionModel.jti == jti)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return auth_session_to_domain(model)
