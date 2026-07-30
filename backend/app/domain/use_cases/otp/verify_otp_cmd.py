from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from ...entities import AuthSession
from ...error_codes import (
    OTP_CONSUMED,
    OTP_EXPIRED,
    OTP_INVALID,
    OTP_LOCKED,
    OTP_SUPERSEDED,
)
from ...ports import (
    AuthSessionCommandRepository,
    ClockService,
    OtpChallengeCommandRepository,
    OtpService,
    TokenService,
    UserCommandRepository,
)
from ...result import Result


@dataclass(frozen=True, slots=True)
class VerifyOtpCommand:
    email: str
    otp: str


@dataclass(frozen=True, slots=True)
class VerifyOtpResult:
    access_token: str
    expires_at: datetime


class VerifyOtpHandler:
    def __init__(
        self,
        user_cmd_repo: UserCommandRepository,
        otp_challenge_cmd_repo: OtpChallengeCommandRepository,
        auth_session_cmd_repo: AuthSessionCommandRepository,
        otp_service: OtpService,
        token_service: TokenService,
        clock_service: ClockService,
        *,
        otp_max_attempts: int,
        access_token_ttl_minutes: int,
    ) -> None:
        self._user_cmd_repo = user_cmd_repo
        self._otp_challenge_cmd_repo = otp_challenge_cmd_repo
        self._auth_session_cmd_repo = auth_session_cmd_repo
        self._otp_service = otp_service
        self._token_service = token_service
        self._clock_service = clock_service
        self._otp_max_attempts = otp_max_attempts
        self._access_token_ttl_minutes = access_token_ttl_minutes

    async def handle(self, command: VerifyOtpCommand) -> Result[VerifyOtpResult]:
        email = command.email.strip().casefold()
        now = self._clock_service.now()
        user = await self._user_cmd_repo.get_by_email_for_update(email)
        if user is None:
            return Result.failure(OTP_INVALID)

        current_user = await self._otp_challenge_cmd_repo.get_current_for_user_for_update(user.id)
        submitted_digest = self._otp_service.digest(email, command.otp)
        matching_otp_challenge = await self._otp_challenge_cmd_repo.get_newest_by_digest_for_update(
            user.id, submitted_digest
        )

        if matching_otp_challenge is not None:
            if matching_otp_challenge.consumed_at is not None:
                return Result.failure(OTP_CONSUMED)
            if matching_otp_challenge.invalidated_at is not None:
                return Result.failure(OTP_SUPERSEDED)
            if matching_otp_challenge.failed_attempt_count >= self._otp_max_attempts:
                return Result.failure(OTP_LOCKED)
            if matching_otp_challenge.expires_at <= now:
                return Result.failure(OTP_EXPIRED)
            if current_user is None or matching_otp_challenge.id != current_user.id:
                return Result.failure(OTP_SUPERSEDED)

            session_jti = uuid4()
            token_expires_at = (now + timedelta(minutes=self._access_token_ttl_minutes)).replace(
                microsecond=0
            )
            await self._otp_challenge_cmd_repo.mark_consumed(matching_otp_challenge.id, now)
            await self._auth_session_cmd_repo.add(
                AuthSession(
                    jti=session_jti,
                    user_id=user.id,
                    expires_at=token_expires_at,
                    revoked_at=None,
                    created_at=now,
                )
            )
            access_token = self._token_service.encode(user.id, session_jti, token_expires_at)
            return Result.success(
                VerifyOtpResult(
                    access_token=access_token,
                    expires_at=token_expires_at,
                )
            )

        if current_user is None:
            return Result.failure(OTP_INVALID)
        if current_user.failed_attempt_count >= self._otp_max_attempts:
            return Result.failure(OTP_LOCKED)
        if current_user.expires_at <= now:
            return Result.failure(OTP_EXPIRED)

        new_count = current_user.failed_attempt_count + 1
        await self._otp_challenge_cmd_repo.set_failed_attempt_count(current_user.id, new_count)
        if new_count >= self._otp_max_attempts:
            return Result.failure(OTP_LOCKED)
        return Result.failure(OTP_INVALID)
