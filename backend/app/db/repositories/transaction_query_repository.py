from sqlalchemy import func, select

from app.domain import (
    PaginatedResult,
    PaginationParams,
    TransactionListItem,
    TransactionQueryRepository,
)

from ..mappers import transaction_to_list_item
from ..models import TransactionModel
from ..session import AsyncSession


class TransactionQueryRepositoryImpl(TransactionQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_admin_page(
        self, params: PaginationParams
    ) -> PaginatedResult[TransactionListItem]:
        offset = params.page_number * params.page_size

        count_stmt = select(func.count()).select_from(TransactionModel)
        total_result = await self.session.execute(count_stmt)
        total_items = total_result.scalar_one()

        stmt = (
            select(TransactionModel)
            .order_by(
                TransactionModel.created_at.desc(),
                TransactionModel.id.desc(),
            )
            .offset(offset)
            .limit(params.page_size)
        )
        result = await self.session.execute(stmt)
        items = [transaction_to_list_item(row) for row in result.scalars().all()]
        return PaginatedResult(total_items=total_items, items=items)
