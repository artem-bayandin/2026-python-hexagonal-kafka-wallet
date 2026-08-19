from app.domain import UserItem, UserReferenceItem

from ..models import UserModel


class UserDbMapper:
    @staticmethod
    def to_domain(model: UserModel) -> UserItem:
        return UserItem(
            id=model.id,
            email=model.email,
            created_at=model.created_at,
        )

    @staticmethod
    def to_model(entity: UserItem) -> UserModel:
        return UserModel(
            id=entity.id,
            email=entity.email,
            created_at=entity.created_at,
        )

    @staticmethod
    def to_reference_item(model: UserModel) -> UserReferenceItem:
        return UserReferenceItem(
            user_id=model.id,
            email=model.email,
        )
