from app.domain import AuthSession

from ..models import AuthSessionModel


def to_domain(model: AuthSessionModel) -> AuthSession:
    return AuthSession(
        jti=model.jti,
        user_id=model.user_id,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        created_at=model.created_at,
    )


def to_model(entity: AuthSession) -> AuthSessionModel:
    return AuthSessionModel(
        jti=entity.jti,
        user_id=entity.user_id,
        expires_at=entity.expires_at,
        revoked_at=entity.revoked_at,
        created_at=entity.created_at,
    )
