from app.domain import UserWalletItem

from ..models import UserWalletModel


def to_domain(model: UserWalletModel) -> UserWalletItem:
    return UserWalletItem(
        id=model.id,
        user_id=model.user_id,
        currency_id=model.currency_id,
        amount=model.amount,
        locked=model.locked_amount,
        updated_at=model.updated_at,
    )
