from app.domain import Transaction, TransactionListItem

from ..models import TransactionModel


def transaction_to_list_item(model: TransactionModel) -> TransactionListItem:
    return TransactionListItem(
        id=model.id,
        type=model.type,
        status=model.status,
        created_at=model.created_at,
    )


def transaction_to_model(entity: Transaction) -> TransactionModel:
    return TransactionModel(
        id=entity.id,
        type=entity.type,
        source_wallet_id=entity.source_wallet_id,
        source_amount=entity.source_amount,
        dest_wallet_id=entity.dest_wallet_id,
        dest_amount=entity.dest_amount,
        status=entity.status,
        created_at=entity.created_at,
    )
