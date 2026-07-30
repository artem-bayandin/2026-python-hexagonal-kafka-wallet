from app.domain import Transaction

from ..models import TransactionModel


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
