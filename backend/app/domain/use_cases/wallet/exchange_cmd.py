from dataclasses import dataclass
from uuid import UUID, uuid4

from ...read_models import TransactionItem
from ...error_codes import (
    SAME_ASSET,
    CREDIT_FAILED,
    INSUFFICIENT_FUNDS,
    INVALID_AMOUNT,
    INVALID_PRECISION,
    UNSUPPORTED_ASSET,
)
from ...ports import (
    ClockService,
    CurrencyQueryRepository,
    CurrentUserProvider,
    TransactionCommandRepository,
    UserWalletCommandRepository,
)
from ...result import Result
from ...value_objects.money import Money


@dataclass(frozen=True, slots=True)
class ExchangeCommand:
    source_asset_label: str
    destination_asset_label: str
    amount_str: str


@dataclass(frozen=True, slots=True)
class ExchangeResult:
    transaction_id: UUID


class ExchangeHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        transactions_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._transactions_repo = transactions_repo
        self._clock_service = clock_service

    async def handle(self, command: ExchangeCommand) -> Result[ExchangeResult]:
        source_label = command.source_asset_label.strip().upper()
        dest_label = command.destination_asset_label.strip().upper()
        if source_label == dest_label:
            return Result.failure(SAME_ASSET)

        source_currency = await self._currency_query_repo.get_by_label(source_label)
        dest_currency = await self._currency_query_repo.get_by_label(dest_label)
        if source_currency is None or dest_currency is None:
            return Result.failure(UNSUPPORTED_ASSET)

        try:
            money = Money.parse(source_label, command.amount_str, source_currency.precision)
            Money.parse(dest_label, command.amount_str, dest_currency.precision)
        except ValueError as error:
            message = str(error)
            if "precision" in message:
                return Result.failure(INVALID_PRECISION)
            if "positive" in message or "Invalid amount" in message:
                return Result.failure(INVALID_AMOUNT)
            return Result.failure(UNSUPPORTED_ASSET)

        user = self._current_user_provider.get()
        now = self._clock_service.now()

        source_wallet = await self._user_wallets_repo.get_or_create_for_update(
            user.id, source_currency.id, uuid4(), now
        )
        dest_wallet = await self._user_wallets_repo.get_or_create_for_update(
            user.id, dest_currency.id, uuid4(), now
        )
        await self._user_wallets_repo.lock_for_update_ordered([source_wallet.id, dest_wallet.id])

        debited = await self._user_wallets_repo.debit(source_wallet.id, money.amount, now)
        if not debited:
            return Result.failure(INSUFFICIENT_FUNDS)

        credited = await self._user_wallets_repo.credit(dest_wallet.id, money.amount, now)
        if not credited:
            return Result.failure(CREDIT_FAILED)

        transaction_id = uuid4()
        await self._transactions_repo.add(
            TransactionItem(
                id=transaction_id,
                type="exchange",
                source_wallet_id=source_wallet.id,
                source_amount=money.amount,
                dest_wallet_id=dest_wallet.id,
                dest_amount=money.amount,
                status="completed",
                created_at=now,
            )
        )
        return Result.success(ExchangeResult(transaction_id=transaction_id))
