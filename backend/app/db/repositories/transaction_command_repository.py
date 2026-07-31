from app.domain import TransactionItem, TransactionCommandRepository

from ..mappers import transaction_to_model
from ..session import AsyncSession


class TransactionCommandRepositoryImpl(TransactionCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, transaction: TransactionItem) -> None:
        self.session.add(transaction_to_model(transaction))
