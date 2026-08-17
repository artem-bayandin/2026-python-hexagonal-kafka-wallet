from uuid import uuid4

from ...error_codes import (
    INVALID_AMOUNT,
    INVALID_PRECISION,
    UNSUPPORTED_ASSET,
    USER_NOT_FOUND,
)
from ...messaging.command_envelope import CommandEnvelope, CommandType
from ...ports import (
    ClockService,
    CurrencyQueryRepository,
    TransactionCommandRepository,
    UserQueryRepository,
    UserWalletCommandRepository,
)
from ...read_models import SubmittedTransactionSpec
from ...result import Result
from ...value_objects import Money
from ..admin.admin_deposit_cmd import AdminDepositCommand
from .submit_transaction import SubmissionInterimHandlerResult

ADMIN_PARTITION_KEY = "admin"


class SubmitDepositHandler:
    def __init__(
        self,
        user_query_repo: UserQueryRepository,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        tx_command_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._user_query_repo = user_query_repo
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._tx_command_repo = tx_command_repo
        self._clock_service = clock_service

    async def validate_and_store_initial_tx(
        self, command: AdminDepositCommand
    ) -> Result[SubmissionInterimHandlerResult]:
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
        request_id = uuid4()
        await self._tx_command_repo.insert_submitted(
            SubmittedTransactionSpec(
                id=uuid4(),
                request_id=request_id,
                type=CommandType.DEPOSIT,
                source_wallet_id=None,
                source_amount=money.amount,
                dest_wallet_id=wallet.id,
                dest_amount=money.amount,
                created_at=now,
                updated_at=now,
                reserve_source_debit=False,
            )
        )
        return Result.success(
            SubmissionInterimHandlerResult(
                request_id=request_id,
                key=ADMIN_PARTITION_KEY,
                envelope=CommandEnvelope(
                    request_id=request_id,
                    type=CommandType.DEPOSIT,
                    submitted_at=now,
                ),
            )
        )


__all__ = ["ADMIN_PARTITION_KEY", "SubmitDepositHandler"]
