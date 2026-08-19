from uuid import uuid4

from ....error_codes import (
    INSUFFICIENT_FUNDS,
    INVALID_AMOUNT,
    INVALID_PRECISION,
    UNSUPPORTED_ASSET,
)
from ....messaging import CommandEnvelope, CommandType
from ....ports import (
    ClockService,
    CurrencyQueryRepository,
    CurrentUserProvider,
    TransactionCommandRepository,
    UserWalletCommandRepository,
)
from ....read_models import SubmittedTransactionSpec
from ....result import Result
from ....value_objects import Money
from ...sub_exec_base.submit_transaction import SubmissionInterimHandlerResult
from .withdraw_cmd import WithdrawCommand


class SubmitWithdrawalHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        tx_command_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._tx_command_repo = tx_command_repo
        self._clock_service = clock_service

    async def validate_and_store_initial_tx(
        self, command: WithdrawCommand
    ) -> Result[SubmissionInterimHandlerResult]:
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
        request_id = uuid4()
        inserted = await self._tx_command_repo.insert_submitted(
            SubmittedTransactionSpec(
                id=uuid4(),
                request_id=request_id,
                type=CommandType.WITHDRAWAL,
                source_wallet_id=wallet.id,
                source_amount=money.amount,
                dest_wallet_id=None,
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
                key=str(user.id),
                envelope=CommandEnvelope(
                    request_id=request_id,
                    type=CommandType.WITHDRAWAL,
                    submitted_at=now,
                ),
            )
        )


__all__ = ["SubmitWithdrawalHandler"]
