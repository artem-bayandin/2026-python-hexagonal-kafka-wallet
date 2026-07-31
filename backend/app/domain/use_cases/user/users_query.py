from dataclasses import dataclass

from ...ports import UserQueryRepository
from ...read_models import UserReferenceItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class UsersQuery:
    pass


class UsersHandler:
    def __init__(self, user_query_repo: UserQueryRepository) -> None:
        self._user_query_repo = user_query_repo

    async def handle(self, _: UsersQuery) -> Result[list[UserReferenceItem]]:
        items = await self._user_query_repo.get_all_ordered_by_email()
        return Result.success(items)
