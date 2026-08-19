from uuid import UUID

from app.domain import TransactionListRow, TransactionItem, TransactionStatus

from ..models import TransactionModel


class TransactionDbMapper:
    @staticmethod
    def to_list_row(
        model: TransactionModel,
        *,
        source_asset: str | None,
        dest_asset: str | None,
        source_precision: int | None,
        dest_precision: int | None,
        source_user_id: UUID | None,
        dest_user_id: UUID | None,
    ) -> TransactionListRow:
        if model.source_wallet_id is None or model.source_amount == 0:
            amount = model.dest_amount
        else:
            amount = model.source_amount

        return TransactionListRow(
            id=model.id,
            request_id=model.request_id,
            type=model.type,
            status=TransactionStatus(model.status),
            error=model.error,
            created_at=model.created_at,
            updated_at=model.updated_at,
            amount=amount,
            source_asset=source_asset,
            dest_asset=dest_asset,
            source_precision=source_precision,
            dest_precision=dest_precision,
            source_user_id=source_user_id,
            dest_user_id=dest_user_id,
        )

    @staticmethod
    def to_domain(model: TransactionModel) -> TransactionItem:
        return TransactionItem(
            id=model.id,
            request_id=model.request_id,
            type=model.type,
            source_wallet_id=model.source_wallet_id,
            source_amount=model.source_amount,
            dest_wallet_id=model.dest_wallet_id,
            dest_amount=model.dest_amount,
            status=TransactionStatus(model.status),
            error=model.error,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(entity: TransactionItem) -> TransactionModel:
        return TransactionModel(
            id=entity.id,
            request_id=entity.request_id,
            type=entity.type,
            source_wallet_id=entity.source_wallet_id,
            source_amount=entity.source_amount,
            dest_wallet_id=entity.dest_wallet_id,
            dest_amount=entity.dest_amount,
            status=entity.status.value,
            error=entity.error,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
