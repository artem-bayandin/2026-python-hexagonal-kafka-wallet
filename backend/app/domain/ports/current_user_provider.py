from typing import Protocol

from ..current_user import CurrentUser


class CurrentUserProvider(Protocol):
    def get(self) -> CurrentUser: ...
