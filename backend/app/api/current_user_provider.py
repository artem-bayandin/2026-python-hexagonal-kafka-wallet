from contextvars import ContextVar, Token

from app.domain import CurrentUser


class ContextVarCurrentUserProvider:
    def __init__(self) -> None:
        self._current_user: ContextVar[CurrentUser] = ContextVar("current_user")

    def bind(self, current_user: CurrentUser) -> Token[CurrentUser]:
        return self._current_user.set(current_user)

    def reset(self, token: Token[CurrentUser]) -> None:
        self._current_user.reset(token)

    def get(self) -> CurrentUser:
        try:
            return self._current_user.get()
        except LookupError as error:
            raise RuntimeError("No current user is bound.") from error
