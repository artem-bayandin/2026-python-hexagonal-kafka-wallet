from dataclasses import dataclass
from uuid import UUID, uuid4

from ...read_models import TransactionItem
from ...value_objects import TransactionStatus, Money
from ...error_codes import (
    INSUFFICIENT_FUNDS,
    INVALID_AMOUNT,
    INVALID_PRECISION,
    UNSUPPORTED_ASSET,
    CREDIT_FAILED,
)
from ...ports import (
    ClockService,
    CurrencyQueryRepository,
    CurrentUserProvider,
    TransactionCommandRepository,
    UserWalletCommandRepository,
)
from ...ports.repositories.admin_wallet_command_repository import (
    AdminWalletCommandRepository,
)
from ...result import Result


@dataclass(frozen=True, slots=True)
class WithdrawCommand:
    asset_label: str
    amount_str: str


@dataclass(frozen=True, slots=True)
class WithdrawResult:
    transaction_id: UUID


class WithdrawHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        admin_wallets_repo: AdminWalletCommandRepository,
        transactions_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._admin_wallets_repo = admin_wallets_repo
        self._transactions_repo = transactions_repo
        self._clock_service = clock_service

    async def handle(self, command: WithdrawCommand) -> Result[WithdrawResult]:
        currency = await self._currency_query_repo.get_by_label(command.asset_label.strip())
        if currency is None:
            return Result.failure(UNSUPPORTED_ASSET)
        try:
            money = Money.parse(command.asset_label, command.amount_str, currency.precision)
        except ValueError as error:
            message = str(error)
            if "precision" in message:
                return Result.failure(INVALID_PRECISION)
            if "positive" in message or "Invalid amount" in message:
                return Result.failure(INVALID_AMOUNT)
            return Result.failure(UNSUPPORTED_ASSET)

        user = self._current_user_provider.get()
        now = self._clock_service.now()

        wallet = await self._user_wallets_repo.get_or_create_for_update(
            user.id, currency.id, uuid4(), now
        )
        await self._admin_wallets_repo.get_for_update(currency.id)

        debited = await self._user_wallets_repo.debit(wallet.id, money.amount, now)
        if not debited:
            return Result.failure(INSUFFICIENT_FUNDS)

        credited = await self._admin_wallets_repo.credit(currency.id, money.amount, now)
        if not credited:
            return Result.failure(CREDIT_FAILED)

        transaction_id = uuid4()
        request_id = uuid4()
        await self._transactions_repo.add(
            TransactionItem(
                id=transaction_id,
                request_id=request_id,
                type="withdrawal",
                source_wallet_id=wallet.id,
                source_amount=money.amount,
                dest_wallet_id=None,
                dest_amount=money.amount,
                status=TransactionStatus.SUCCEEDED,
                error=None,
                created_at=now,
                updated_at=now,
            )
        )
        return Result.success(WithdrawResult(transaction_id=transaction_id))
