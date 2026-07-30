from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import aliased

from app.domain import (
    PaginatedResult,
    PaginationParams,
    TransactionListItem,
    TransactionQueryRepository,
)

from ..mappers import transaction_to_list_item
from ..models import CurrencyModel, TransactionModel, UserWalletModel
from ..session import AsyncSession

SourceWalletModel = aliased(UserWalletModel, name="source_wallet")
DestWalletModel = aliased(UserWalletModel, name="dest_wallet")
SourceCurrencyModel = aliased(CurrencyModel, name="source_currency")
DestCurrencyModel = aliased(CurrencyModel, name="dest_currency")


class TransactionQueryRepositoryImpl(TransactionQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _list_item_select(self) -> Select[Any]:
        return (
            select(
                TransactionModel,
                SourceCurrencyModel.label,
                DestCurrencyModel.label,
            )
            .outerjoin(
                SourceWalletModel,
                TransactionModel.source_wallet_id == SourceWalletModel.id,
            )
            .outerjoin(
                DestWalletModel,
                TransactionModel.dest_wallet_id == DestWalletModel.id,
            )
            .outerjoin(
                SourceCurrencyModel,
                SourceWalletModel.currency_id == SourceCurrencyModel.id,
            )
            .outerjoin(
                DestCurrencyModel,
                DestWalletModel.currency_id == DestCurrencyModel.id,
            )
        )

    def _rows_to_list_items(self, rows: Sequence[Any]) -> list[TransactionListItem]:
        return [
            transaction_to_list_item(
                row[0],
                source_asset=row[1],
                dest_asset=row[2],
            )
            for row in rows
        ]

    async def list_admin_page(
        self, params: PaginationParams
    ) -> PaginatedResult[TransactionListItem]:
        offset = params.page_number * params.page_size

        count_stmt = select(func.count()).select_from(TransactionModel)
        total_result = await self.session.execute(count_stmt)
        total_items = total_result.scalar_one()

        stmt = (
            self._list_item_select()
            .order_by(
                TransactionModel.created_at.desc(),
                TransactionModel.id.desc(),
            )
            .offset(offset)
            .limit(params.page_size)
        )
        result = await self.session.execute(stmt)
        items = self._rows_to_list_items(result.all())
        return PaginatedResult(total_items=total_items, items=items)

    async def list_user_page(
        self, user_id: UUID, params: PaginationParams
    ) -> PaginatedResult[TransactionListItem]:
        offset = params.page_number * params.page_size
        wallet_ids = (
            select(UserWalletModel.id).where(UserWalletModel.user_id == user_id)
        ).scalar_subquery()

        ownership = or_(
            TransactionModel.source_wallet_id.in_(wallet_ids),
            TransactionModel.dest_wallet_id.in_(wallet_ids),
        )

        count_stmt = select(func.count()).select_from(TransactionModel).where(ownership)
        total_items = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            self._list_item_select()
            .where(ownership)
            .order_by(
                TransactionModel.created_at.desc(),
                TransactionModel.id.desc(),
            )
            .offset(offset)
            .limit(params.page_size)
        )
        result = await self.session.execute(stmt)
        items = self._rows_to_list_items(result.all())
        return PaginatedResult(total_items=total_items, items=items)
