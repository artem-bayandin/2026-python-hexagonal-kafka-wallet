from uuid import uuid4

from ....error_codes import (
    INSUFFICIENT_FUNDS,
    INVALID_AMOUNT,
    INVALID_PRECISION,
    TRANSFER_TO_SELF,
    UNSUPPORTED_ASSET,
    USER_NOT_FOUND,
)
from ....messaging import CommandEnvelope, CommandType
from ....ports import (
    ClockService,
    CurrencyQueryRepository,
    CurrentUserProvider,
    TransactionCommandRepository,
    UserQueryRepository,
    UserWalletCommandRepository,
)
from ....read_models import SubmittedTransactionSpec
from ....result import Result
from ....value_objects import Money
from ...sub_exec_base.submit_transaction import SubmissionInterimHandlerResult
from .transfer_cmd import TransferCommand


class SubmitTransferHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        user_query_repo: UserQueryRepository,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        tx_command_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._user_query_repo = user_query_repo
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._tx_command_repo = tx_command_repo
        self._clock_service = clock_service

    async def validate_and_store_initial_tx(
        self, command: TransferCommand
    ) -> Result[SubmissionInterimHandlerResult]:
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
        request_id = uuid4()
        inserted = await self._tx_command_repo.insert_submitted(
            SubmittedTransactionSpec(
                id=uuid4(),
                request_id=request_id,
                type=CommandType.TRANSFER,
                source_wallet_id=source_wallet.id,
                source_amount=money.amount,
                dest_wallet_id=dest_wallet.id,
                dest_amount=money.amount,
                created_at=now,
                updated_at=now,
                reserve_source_debit=True,
            )
        )
        if not inserted:
            return Result.failure(INSUFFICIENT_FUNDS)

        return Result.success(
            SubmissionInterimHandlerResult(
                request_id=request_id,
                key=str(sender.id),
                envelope=CommandEnvelope(
                    request_id=request_id,
                    type=CommandType.TRANSFER,
                    submitted_at=now,
                ),
            )
        )


__all__ = ["SubmitTransferHandler"]
