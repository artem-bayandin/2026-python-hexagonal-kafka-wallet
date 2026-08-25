from sqlalchemy import select

from app.domain import CurrencyItem, CurrencyCatalogItem, CurrencyQueryRepository

from ..mappers import CurrencyDbMapper
from ..models import CurrencyModel
from ..session import AsyncSession


class CurrencyQueryRepositoryImpl(CurrencyQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all_ordered_by_label(self) -> list[CurrencyCatalogItem]:
        stmt = select(CurrencyModel).order_by(CurrencyModel.label.asc())
        result = await self.session.execute(stmt)
        return [CurrencyDbMapper.to_catalog_item(row) for row in result.scalars().all()]

    async def get_by_label(self, label: str) -> CurrencyItem | None:
        stmt = select(CurrencyModel).where(CurrencyModel.label == label.upper())
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return CurrencyDbMapper.to_domain(model)
