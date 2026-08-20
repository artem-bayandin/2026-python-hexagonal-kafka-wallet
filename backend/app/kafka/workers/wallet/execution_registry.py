from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.auth import SystemClock
from app.db import (
    AdminWalletCommandRepositoryImpl,
    TransactionCommandRepositoryImpl,
    UserWalletCommandRepositoryImpl,
)
from app.domain import (
    ClockService,
    WalletTxType,
    ExecuteDepositHandler,
    ExecuteExchangeHandler,
    ExecuteTransferHandler,
    ExecuteWithdrawalHandler,
    ExecutionHandlerRegistry,
)


def build_wallet_execution_registry(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    clock: ClockService | None = None,
) -> ExecutionHandlerRegistry:
    clock_service = clock if clock is not None else SystemClock()
    registry = ExecutionHandlerRegistry()
    registry.register(
        WalletTxType.DEPOSIT,
        ExecuteDepositHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            clock_service,
        ),
    )
    registry.register(
        WalletTxType.WITHDRAWAL,
        ExecuteWithdrawalHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            AdminWalletCommandRepositoryImpl,
            clock_service,
        ),
    )
    registry.register(
        WalletTxType.EXCHANGE,
        ExecuteExchangeHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            clock_service,
        ),
    )
    registry.register(
        WalletTxType.TRANSFER,
        ExecuteTransferHandler(
            session_factory,
            TransactionCommandRepositoryImpl,
            UserWalletCommandRepositoryImpl,
            clock_service,
        ),
    )
    return registry
