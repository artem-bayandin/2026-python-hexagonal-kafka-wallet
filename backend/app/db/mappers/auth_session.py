from app.domain import AuthSessionItem

from ..models import AuthSessionModel


class AuthSessionDbMapper:
    @staticmethod
    def to_domain(model: AuthSessionModel) -> AuthSessionItem:
        return AuthSessionItem(
            jti=model.jti,
            user_id=model.user_id,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            created_at=model.created_at,
        )

    @staticmethod
    def to_model(entity: AuthSessionItem) -> AuthSessionModel:
        return AuthSessionModel(
            jti=entity.jti,
            user_id=entity.user_id,
            expires_at=entity.expires_at,
            revoked_at=entity.revoked_at,
            created_at=entity.created_at,
        )
