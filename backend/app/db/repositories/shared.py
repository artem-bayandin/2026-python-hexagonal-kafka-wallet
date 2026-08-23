from uuid import UUID

from sqlalchemy import ColumnElement, or_, select

from ..models import TransactionModel, UserWalletModel


def tx_visible_to_user_clause(user_id: UUID) -> ColumnElement[bool]:
    wallet_ids = select(UserWalletModel.id).where(UserWalletModel.user_id == user_id)
    wallet_ids_subquery = wallet_ids.scalar_subquery()
    return or_(
        TransactionModel.source_wallet_id.in_(wallet_ids_subquery),
        TransactionModel.dest_wallet_id.in_(wallet_ids_subquery),
    )
