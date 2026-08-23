from uuid import UUID

from sqlalchemy import select, tuple_

from app.domain import TransactionStatus
from app.notifier import StatusCursor, StatusEventRepository, TransactionStatusEvent

from ..models import TransactionModel
from ..session import AsyncSession
from .shared import tx_visible_to_user_clause


class StatusEventRepositoryImpl(StatusEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_status_events_after(
        self, user_id: UUID, after: StatusCursor | None, limit: int
    ) -> list[TransactionStatusEvent]:
        stmt = (
            select(TransactionModel)
            .where(tx_visible_to_user_clause(user_id))
            .order_by(TransactionModel.updated_at.asc(), TransactionModel.id.asc())
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(
                tuple_(TransactionModel.updated_at, TransactionModel.id)
                > (after.updated_at, after.transaction_id)
            )
        models = (await self.session.execute(stmt)).scalars().all()
        return [_to_status_event(model) for model in models]

    async def get_status_high_water(self, user_id: UUID) -> StatusCursor | None:
        stmt = (
            select(TransactionModel.updated_at, TransactionModel.id)
            .where(tx_visible_to_user_clause(user_id))
            .order_by(TransactionModel.updated_at.desc(), TransactionModel.id.desc())
            .limit(1)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return StatusCursor(updated_at=row[0], transaction_id=row[1])


def _to_status_event(model: TransactionModel) -> TransactionStatusEvent:
    return TransactionStatusEvent(
        request_id=model.request_id,
        status=TransactionStatus(model.status),
        type=model.type,
        error=model.error,
        updated_at=model.updated_at,
        transaction_id=model.id,
    )
