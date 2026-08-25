from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.domain import UserItem, UserCommandRepository

from ..mappers import UserDbMapper
from ..models import UserModel
from ..session import AsyncSession


class UserCommandRepositoryImpl(UserCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_by_email_if_not_exists(
        self, email: str, user_id: UUID, created_at: datetime
    ) -> None:
        stmt = (
            insert(UserModel)
            .values(id=user_id, email=email, created_at=created_at)
            .on_conflict_do_nothing(index_elements=[UserModel.email])
        )
        await self.session.execute(stmt)

    async def get_by_email_for_update(self, email: str) -> UserItem | None:
        stmt = select(UserModel).where(UserModel.email == email).with_for_update()
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return UserDbMapper.to_domain(model)
