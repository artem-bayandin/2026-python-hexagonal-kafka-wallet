from dataclasses import dataclass

from ...current_user import CurrentUser
from ...error_codes import AUTHENTICATION_FAILED
from ...ports import (
    AuthSessionQueryRepository,
    ClockService,
    TokenService,
    UserQueryRepository,
)
from ...result import Result


@dataclass(frozen=True, slots=True)
class CurrentUserQuery:
    token: str


class CurrentUserHandler:
    def __init__(
        self,
        token_service: TokenService,
        clock_service: ClockService,
        auth_session_query_repo: AuthSessionQueryRepository,
        user_query_repo: UserQueryRepository,
    ) -> None:
        self._token_service = token_service
        self._clock_service = clock_service
        self._auth_session_query_repo = auth_session_query_repo
        self._user_query_repo = user_query_repo

    async def handle(self, query: CurrentUserQuery) -> Result[CurrentUser]:
        claims_result = self._token_service.decode(query.token)
        if not claims_result.is_success:
            return Result.failure(
                AUTHENTICATION_FAILED,
                reason=claims_result.reason,
            )
        claims = claims_result.data
        assert claims is not None

        now = self._clock_service.now()
        session = await self._auth_session_query_repo.get_by_jti(claims.session_jti)
        if session is None:
            return Result.failure(AUTHENTICATION_FAILED)
        if session.user_id != claims.user_id:
            return Result.failure(AUTHENTICATION_FAILED)
        if session.revoked_at is not None or session.expires_at <= now:
            return Result.failure(AUTHENTICATION_FAILED)
        if session.expires_at != claims.expires_at:
            return Result.failure(AUTHENTICATION_FAILED)

        user = await self._user_query_repo.get_by_id(claims.user_id)
        if user is None:
            return Result.failure(AUTHENTICATION_FAILED)
        return Result.success(
            CurrentUser(
                id=user.id,
                email=user.email,
                session_jti=session.jti,
            )
        )
