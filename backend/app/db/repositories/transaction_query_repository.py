from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import aliased

from app.domain import (
    PaginatedResult,
    PaginationParams,
    TransactionItem,
    TransactionQueryRepository,
    TransactionListRow,
)

from ..mappers import TransactionDbMapper
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
                SourceCurrencyModel.precision,
                DestCurrencyModel.precision,
                SourceWalletModel.user_id,
                DestWalletModel.user_id,
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

    def _rows_to_list_rows(self, rows: Sequence[Any]) -> list[TransactionListRow]:
        return [
            TransactionDbMapper.to_list_row(
                row[0],
                source_asset=row[1],
                dest_asset=row[2],
                source_precision=row[3],
                dest_precision=row[4],
                source_user_id=row[5],
                dest_user_id=row[6],
            )
            for row in rows
        ]

    async def get_by_request_id(self, request_id: UUID) -> TransactionItem | None:
        stmt = select(TransactionModel).where(TransactionModel.request_id == request_id)
        model = (await self.session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        return TransactionDbMapper.to_domain(model)

    async def get_all_transactions_page(
        self, params: PaginationParams
    ) -> PaginatedResult[TransactionListRow]:
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
        items = self._rows_to_list_rows(result.all())
        return PaginatedResult(total_items=total_items, items=items)

    async def get_user_transactions_page(
        self, user_id: UUID, params: PaginationParams
    ) -> PaginatedResult[TransactionListRow]:
        offset = params.page_number * params.page_size
        wallet_ids = select(UserWalletModel.id).where(UserWalletModel.user_id == user_id)
        wallet_ids_subquery = wallet_ids.scalar_subquery()

        ownership = or_(
            TransactionModel.source_wallet_id.in_(wallet_ids_subquery),
            TransactionModel.dest_wallet_id.in_(wallet_ids_subquery),
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
        items = self._rows_to_list_rows(result.all())
        return PaginatedResult(total_items=total_items, items=items)
