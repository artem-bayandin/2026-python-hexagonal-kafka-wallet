from dataclasses import dataclass
from uuid import UUID, uuid4

from ...read_models import TransactionItem
from ...value_objects import TransactionStatus, Money
from ...error_codes import (
    INVALID_AMOUNT,
    INVALID_PRECISION,
    UNSUPPORTED_ASSET,
    USER_NOT_FOUND,
)
from ...ports import (
    ClockService,
    CurrencyQueryRepository,
    TransactionCommandRepository,
    UserQueryRepository,
    UserWalletCommandRepository,
)
from ...result import Result


@dataclass(frozen=True, slots=True)
class AdminDepositCommand:
    email: str
    asset_label: str
    amount_str: str


@dataclass(frozen=True, slots=True)
class AdminDepositResult:
    transaction_id: UUID


class AdminDepositHandler:
    def __init__(
        self,
        user_query_repo: UserQueryRepository,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        transactions_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._user_query_repo = user_query_repo
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._transactions_repo = transactions_repo
        self._clock_service = clock_service

    async def handle(self, command: AdminDepositCommand) -> Result[AdminDepositResult]:
        email = command.email.strip().casefold()
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

        user = await self._user_query_repo.get_by_email(email)
        if user is None:
            return Result.failure(USER_NOT_FOUND)

        now = self._clock_service.now()
        wallet = await self._user_wallets_repo.get_or_create_for_update(
            user.id, currency.id, uuid4(), now
        )
        await self._user_wallets_repo.credit(wallet.id, money.amount, now)
        transaction_id = uuid4()
        request_id = uuid4()
        await self._transactions_repo.add(
            TransactionItem(
                id=transaction_id,
                request_id=request_id,
                type="deposit",
                source_wallet_id=None,
                source_amount=money.amount,
                dest_wallet_id=wallet.id,
                dest_amount=money.amount,
                status=TransactionStatus.SUCCEEDED,
                error=None,
                created_at=now,
                updated_at=now,
            )
        )
        return Result.success(AdminDepositResult(transaction_id=transaction_id))
