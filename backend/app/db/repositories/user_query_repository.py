from uuid import UUID

from sqlalchemy import select

from app.domain import UserItem, UserQueryRepository, UserReferenceItem

from ..mappers import user_to_domain, user_to_reference_item
from ..models import UserModel
from ..session import AsyncSession


class UserQueryRepositoryImpl(UserQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> UserItem | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return user_to_domain(model)

    async def get_by_email(self, email: str) -> UserItem | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return user_to_domain(model)

    async def get_all_ordered_by_email(self) -> list[UserReferenceItem]:
        stmt = select(UserModel).order_by(UserModel.email.asc())
        result = await self.session.execute(stmt)
        return [user_to_reference_item(row) for row in result.scalars().all()]
