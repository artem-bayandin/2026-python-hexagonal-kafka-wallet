from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.domain import User, UserRepository

from ..mappers import user_to_domain
from ..models import UserModel
from ..session import AsyncSession


class UserRepositoryImpl(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_by_email(
        self
        , email: str
        , user_id: UUID
        , created_at: datetime
    ) -> None:
        stmt = (
            insert(UserModel)
            .values(id=user_id, email=email, created_at=created_at)
            .on_conflict_do_nothing(index_elements=[UserModel.email])
        )
        await self.session.execute(stmt)

    async def get_by_email_for_update(self, email: str) -> User:
        stmt = (
            select(UserModel)
            .where(UserModel.email == email)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return user_to_domain(result.scalar_one())
