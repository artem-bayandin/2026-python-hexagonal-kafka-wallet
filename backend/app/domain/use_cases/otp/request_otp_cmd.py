from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from ...read_models import OtpChallengeItem
from ...ports import (
    ClockService,
    OtpChallengeCommandRepository,
    OtpService,
    UserCommandRepository,
)
from ...result import Result


@dataclass(frozen=True, slots=True)
class RequestOtpCommand:
    email: str


@dataclass(frozen=True, slots=True)
class RequestOtpResult:
    expires_at: datetime
    demo_otp: str | None


class RequestOtpHandler:
    def __init__(
        self,
        user_cmd_repo: UserCommandRepository,
        otp_challenge_cmd_repo: OtpChallengeCommandRepository,
        otp_service: OtpService,
        clock_service: ClockService,
        *,
        otp_ttl_seconds: int,
        include_demo_otp: bool,
    ) -> None:
        self._user_cmd_repo = user_cmd_repo
        self._otp_challenge_cmd_repo = otp_challenge_cmd_repo
        self._otp_service = otp_service
        self._clock_service = clock_service
        self._otp_ttl_seconds = otp_ttl_seconds
        self._include_demo_otp = include_demo_otp

    async def handle(self, command: RequestOtpCommand) -> Result[RequestOtpResult]:
        email = command.email.strip().casefold()
        now = self._clock_service.now()
        proposed_user_id = uuid4()

        await self._user_cmd_repo.create_by_email_if_not_exists(email, proposed_user_id, now)
        user = await self._user_cmd_repo.get_by_email_for_update(email)
        assert user is not None

        await self._otp_challenge_cmd_repo.invalidate_current_for_user(user.id, now)

        code = self._otp_service.generate_code()
        expires_at = now + timedelta(seconds=self._otp_ttl_seconds)
        await self._otp_challenge_cmd_repo.add(
            OtpChallengeItem(
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
            RequestOtpResult(
                expires_at=expires_at,
                demo_otp=code if self._include_demo_otp else None,
            )
        )
