from app.domain import OtpChallengeItem

from ..models import OtpChallengeModel


class OtpChallengeDbMapper:
    @staticmethod
    def to_domain(model: OtpChallengeModel) -> OtpChallengeItem:
        return OtpChallengeItem(
            id=model.id,
            user_id=model.user_id,
            otp_digest=model.otp_digest,
            expires_at=model.expires_at,
            failed_attempt_count=model.failed_attempt_count,
            consumed_at=model.consumed_at,
            invalidated_at=model.invalidated_at,
            created_at=model.created_at,
        )

    @staticmethod
    def to_model(entity: OtpChallengeItem) -> OtpChallengeModel:
        return OtpChallengeModel(
            id=entity.id,
            user_id=entity.user_id,
            otp_digest=entity.otp_digest,
            expires_at=entity.expires_at,
            failed_attempt_count=entity.failed_attempt_count,
            consumed_at=entity.consumed_at,
            invalidated_at=entity.invalidated_at,
            created_at=entity.created_at,
        )
