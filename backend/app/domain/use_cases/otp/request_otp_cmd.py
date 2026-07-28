from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from ...entities import OtpChallenge
from ...ports import OtpChallengeRepository, UserRepository, ClockService, OtpService
from ...result import Result


@dataclass(frozen=True, slots=True)
class RequestOtpCommand:
    email: str


@dataclass(frozen=True, slots=True)
class RequestOtpData:
    expires_at: datetime
    demo_otp: str | None


class RequestOtpHandler:
    def __init__(
        self,
        users_repo: UserRepository,
        otp_challenges_repo: OtpChallengeRepository,
        otp_service: OtpService,
        clock_service: ClockService,
        *,
        otp_ttl_seconds: int,
        include_demo_otp: bool,
    ) -> None:
        self._users_repo = users_repo
        self._otp_challenges_repo = otp_challenges_repo
        self._otp_service = otp_service
        self._clock_service = clock_service
        self._otp_ttl_seconds = otp_ttl_seconds
        self._include_demo_otp = include_demo_otp

    async def handle(self, command: RequestOtpCommand) -> Result[RequestOtpData]:
        email = command.email.strip().casefold()
        now = self._clock_service.now()
        proposed_user_id = uuid4()

        await self._users_repo.ensure_by_email(email, proposed_user_id, now)
        user = await self._users_repo.get_by_email_for_update(email)

        await self._otp_challenges_repo.invalidate_current_for_user(user.id, now)

        code = self._otp_service.generate_code()
        expires_at = now + timedelta(seconds=self._otp_ttl_seconds)
        await self._otp_challenges_repo.add(
            OtpChallenge(
                id=uuid4(),
                user_id=user.id,
                otp_digest=self._otp_service.digest(email, code),
                expires_at=expires_at,
                failed_attempt_count=0,
                consumed_at=None,
                invalidated_at=None,
                created_at=now,
            )
        )

        return Result.success(
            RequestOtpData(
                expires_at=expires_at,
                demo_otp=code if self._include_demo_otp else None,
            )
        )
