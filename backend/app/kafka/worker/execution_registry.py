from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.auth import SystemClock
from app.db import (
    AdminWalletCommandRepositoryImpl,
    AsyncSession,
    TransactionCommandRepositoryImpl,
    UserWalletCommandRepositoryImpl,
    build_session_factory,
)
from app.domain import (
    CommandType,
    ExecuteDepositHandler,
    ExecuteExchangeHandler,
    ExecuteTransferHandler,
    ExecuteWithdrawalHandler,
    ExecutionHandlerRegistry,
)


def build_worker_execution_registry(engine: AsyncEngine) -> ExecutionHandlerRegistry:
    session_factory: async_sessionmaker[AsyncSession] = build_session_factory(engine)
    registry = ExecutionHandlerRegistry()
    registry.register(
        CommandType.DEPOSIT,
        ExecuteDepositHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            SystemClock(),
        ),
    )
    registry.register(
        CommandType.WITHDRAWAL,
        ExecuteWithdrawalHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            AdminWalletCommandRepositoryImpl,
            SystemClock(),
        ),
    )
    registry.register(
        CommandType.EXCHANGE,
        ExecuteExchangeHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            SystemClock(),
        ),
    )
    registry.register(
        CommandType.TRANSFER,
        ExecuteTransferHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            SystemClock(),
        ),
    )
    return registry


__all__ = ["build_worker_execution_registry"]
