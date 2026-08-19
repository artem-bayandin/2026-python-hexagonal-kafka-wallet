from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....ports import ClockService, TransactionCommandRepository, UserWalletCommandRepository
from ....read_models import TransactionItem
from ....safe_errors import SAFE_EXECUTION_FAILED
from ....value_objects import TransactionStatus
from ...sub_exec_base.execute_cmd import PoisonExecutionError


class ExecuteDepositHandler:
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
            completed = await self._execute_deposit(
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

    async def _execute_deposit(
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
        if locked.type != "deposit" or locked.dest_wallet_id is None:
            return 0

        now = self._clock_service.now()
        wallets = await wallet_command_repo.lock_for_update_ordered([locked.dest_wallet_id])
        if len(wallets) != 1:
            return 0

        if not await wallet_command_repo.credit(
            locked.dest_wallet_id,
            locked.dest_amount,
            now,
        ):
            return 0

        return await tx_command_repo.complete_if_in_progress(request_id, None)
