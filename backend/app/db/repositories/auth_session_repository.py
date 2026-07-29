from app.domain import AuthSession, AuthSessionRepository

from ..mappers import auth_session_to_model
from ..session import AsyncSession


class AuthSessionRepositoryImpl(AuthSessionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, session: AuthSession) -> None:
        self.session.add(auth_session_to_model(session))
