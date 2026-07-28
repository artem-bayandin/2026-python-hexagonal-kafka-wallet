from app.domain import User

from ..models import UserModel


def to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        created_at=model.created_at,
    )


def to_model(entity: User) -> UserModel:
    return UserModel(
        id=entity.id,
        email=entity.email,
        created_at=entity.created_at,
    )
