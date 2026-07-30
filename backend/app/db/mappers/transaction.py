from app.domain import Transaction, TransactionListItem

from ..models import TransactionModel


def transaction_to_list_item(
    model: TransactionModel,
    *,
    source_asset: str | None,
    dest_asset: str | None,
) -> TransactionListItem:
    if model.source_wallet_id is None or model.source_amount == 0:
        amount = model.dest_amount
    else:
        amount = model.source_amount

    return TransactionListItem(
        id=model.id,
        type=model.type,
        status=model.status,
        created_at=model.created_at,
        amount=amount,
        source_asset=source_asset,
        dest_asset=dest_asset,
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
