from app.domain import UserWallet

from ..models import UserWalletModel


def user_wallet_to_domain(model: UserWalletModel) -> UserWallet:
    return UserWallet(
        id=model.id,
        user_id=model.user_id,
        currency_id=model.currency_id,
        amount=model.amount,
        updated_at=model.updated_at,
    )
