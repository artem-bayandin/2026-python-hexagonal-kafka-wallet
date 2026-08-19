from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....ports import (
    ClockService,
    TransactionCommandRepository,
    UserWalletCommandRepository,
)
from ....read_models import TransactionItem
from ....safe_errors import SAFE_EXECUTION_FAILED
from ....value_objects import TransactionStatus
from ...sub_exec_base.execute_cmd import PoisonExecutionError


class ExecuteExchangeHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tx_command_repo_factory: Callable[[AsyncSession], TransactionCommandRepository],
        wallet_command_repo_factory: Callable[[AsyncSession], UserWalletCommandRepository],
        clock_service: ClockService,
    ) -> None:
        self._session_factory = session_factory
        self._tx_command_repo_factory = tx_command_repo_factory
        self._wallet_command_repo_factory = wallet_command_repo_factory
        self._clock_service = clock_service

    async def execute(self, transaction: TransactionItem) -> None:
        async with self._session_factory() as session, session.begin():
            tx_command_repo = self._tx_command_repo_factory(session)
            wallet_command_repo = self._wallet_command_repo_factory(session)
            completed = await self._execute_exchange(
                tx_command_repo,
                wallet_command_repo,
                transaction.request_id,
            )
            if completed == 1:
                return
            reloaded = await tx_command_repo.lock_by_request_id(transaction.request_id)
            if reloaded is not None and reloaded.status == TransactionStatus.SUCCEEDED:
                return
            raise PoisonExecutionError(SAFE_EXECUTION_FAILED)

    async def _execute_exchange(
        self,
        tx_command_repo: TransactionCommandRepository,
        wallet_command_repo: UserWalletCommandRepository,
        request_id: UUID,
    ) -> int:
        locked = await tx_command_repo.lock_by_request_id(request_id)
        if locked is None:
            return 0
        if locked.status != TransactionStatus.IN_PROGRESS:
            return 0
        if (
            locked.type != "exchange"
            or locked.source_wallet_id is None
            or locked.dest_wallet_id is None
            or locked.source_amount != locked.dest_amount
        ):
            return 0

        now = self._clock_service.now()
        wallets = await wallet_command_repo.lock_for_update_ordered(
            [locked.source_wallet_id, locked.dest_wallet_id]
        )
        if len(wallets) != 2:
            return 0

        wallet_by_id = {wallet.id: wallet for wallet in wallets}
        source_wallet = wallet_by_id.get(locked.source_wallet_id)
        dest_wallet = wallet_by_id.get(locked.dest_wallet_id)
        if source_wallet is None or dest_wallet is None:
            return 0
        if source_wallet.currency_id == dest_wallet.currency_id:
            return 0

        if not await wallet_command_repo.settle_debit(
            locked.source_wallet_id,
            locked.source_amount,
            now,
        ):
            return 0

        if not await wallet_command_repo.credit(
            locked.dest_wallet_id,
            locked.dest_amount,
            now,
        ):
            return 0

        return await tx_command_repo.complete_if_in_progress(request_id, None)


__all__ = ["ExecuteExchangeHandler"]
