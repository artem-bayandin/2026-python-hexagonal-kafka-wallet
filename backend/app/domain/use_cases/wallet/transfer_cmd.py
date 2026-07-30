from dataclasses import dataclass
from uuid import UUID, uuid4

from ...entities import Transaction
from ...error_codes import (
    INSUFFICIENT_FUNDS,
    INVALID_AMOUNT,
    INVALID_PRECISION,
    UNSUPPORTED_ASSET,
    USER_NOT_FOUND,
)
from ...ports import (
    ClockService,
    CurrencyQueryRepository,
    CurrentUserProvider,
    TransactionCommandRepository,
    UserCommandRepository,
    UserWalletCommandRepository,
)
from ...result import Result
from ...value_objects.money import Money


@dataclass(frozen=True, slots=True)
class TransferCommand:
    recipient_email: str
    asset_label: str
    amount_str: str


@dataclass(frozen=True, slots=True)
class TransferResult:
    transaction_id: UUID


class TransferHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        user_cmd_repo: UserCommandRepository,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        transactions_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._user_cmd_repo = user_cmd_repo
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._transactions_repo = transactions_repo
        self._clock_service = clock_service

    async def handle(self, command: TransferCommand) -> Result[TransferResult]:
        email = command.recipient_email.strip().casefold()
        currency = await self._currency_query_repo.get_by_label(command.asset_label.strip().upper())
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

        sender = self._current_user_provider.get()
        if email == sender.email.casefold():
            return Result.failure(INVALID_AMOUNT)

        recipient = await self._user_cmd_repo.get_by_normalized_email(email)
        if recipient is None:
            return Result.failure(USER_NOT_FOUND)

        now = self._clock_service.now()
        source_wallet = await self._user_wallets_repo.get_or_create_for_update(
            sender.id, currency.id, uuid4(), now
        )
        dest_wallet = await self._user_wallets_repo.get_or_create_for_update(
            recipient.id, currency.id, uuid4(), now
        )
        await self._user_wallets_repo.lock_for_update_ordered([source_wallet.id, dest_wallet.id])

        debited = await self._user_wallets_repo.debit(source_wallet.id, money.amount, now)
        if not debited:
            return Result.failure(INSUFFICIENT_FUNDS)

        await self._user_wallets_repo.credit(dest_wallet.id, money.amount, now)
        transaction_id = uuid4()
        await self._transactions_repo.add(
            Transaction(
                id=transaction_id,
                type="transfer",
                source_wallet_id=source_wallet.id,
                source_amount=money.amount,
                dest_wallet_id=dest_wallet.id,
                dest_amount=money.amount,
                status="completed",
                created_at=now,
            )
        )
        return Result.success(TransferResult(transaction_id=transaction_id))
