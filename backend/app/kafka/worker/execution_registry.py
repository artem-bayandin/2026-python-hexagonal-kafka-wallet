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
    WalletTxType,
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
        WalletTxType.DEPOSIT,
        ExecuteDepositHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            SystemClock(),
        ),
    )
    registry.register(
        WalletTxType.WITHDRAWAL,
        ExecuteWithdrawalHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            AdminWalletCommandRepositoryImpl,
            SystemClock(),
        ),
    )
    registry.register(
        WalletTxType.EXCHANGE,
        ExecuteExchangeHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            SystemClock(),
        ),
    )
    registry.register(
        WalletTxType.TRANSFER,
        ExecuteTransferHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            SystemClock(),
        ),
    )
    return registry
