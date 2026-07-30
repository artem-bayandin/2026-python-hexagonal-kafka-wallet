from dataclasses import dataclass

from ...error_codes import AUTHENTICATION_FAILED
from ...ports import AuthSessionCommandRepository, ClockService, CurrentUserProvider
from ...result import Result


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    pass


class LogoutHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        auth_session_cmd_repo: AuthSessionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._auth_session_cmd_repo = auth_session_cmd_repo
        self._clock_service = clock_service

    async def handle(self, _: LogoutCommand) -> Result[None]:
        current_user = self._current_user_provider.get()
        changed = await self._auth_session_cmd_repo.revoke(
            current_user.session_jti, self._clock_service.now()
        )
        if not changed:
            return Result.failure(AUTHENTICATION_FAILED)
        return Result.success()
