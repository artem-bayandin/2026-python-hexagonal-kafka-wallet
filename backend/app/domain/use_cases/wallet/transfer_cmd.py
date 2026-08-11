from dataclasses import dataclass
from uuid import UUID, uuid4

from ...read_models import TransactionItem
from ...value_objects import TransactionStatus, Money
from ...error_codes import (
    INSUFFICIENT_FUNDS,
    INVALID_AMOUNT,
    INVALID_PRECISION,
    UNSUPPORTED_ASSET,
    USER_NOT_FOUND,
    TRANSFER_TO_SELF,
    CREDIT_FAILED,
)
from ...ports import (
    ClockService,
    CurrencyQueryRepository,
    CurrentUserProvider,
    TransactionCommandRepository,
    UserQueryRepository,
    UserWalletCommandRepository,
)
from ...result import Result


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
        user_query_repo: UserQueryRepository,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        transactions_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._user_query_repo = user_query_repo
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._transactions_repo = transactions_repo
        self._clock_service = clock_service

    async def handle(self, command: TransferCommand) -> Result[TransferResult]:
        email = command.recipient_email.strip().casefold()
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

        sender = self._current_user_provider.get()
        if email == sender.email.casefold():
            return Result.failure(TRANSFER_TO_SELF)

        recipient = await self._user_query_repo.get_by_email(email)
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

        credited = await self._user_wallets_repo.credit(dest_wallet.id, money.amount, now)
        if not credited:
            return Result.failure(CREDIT_FAILED)

        transaction_id = uuid4()
        request_id = uuid4()
        await self._transactions_repo.add(
            TransactionItem(
                id=transaction_id,
                request_id=request_id,
                type="transfer",
                source_wallet_id=source_wallet.id,
                source_amount=money.amount,
                dest_wallet_id=dest_wallet.id,
                dest_amount=money.amount,
                status=TransactionStatus.SUCCEEDED,
                error=None,
                created_at=now,
                updated_at=now,
            )
        )
        return Result.success(TransferResult(transaction_id=transaction_id))
