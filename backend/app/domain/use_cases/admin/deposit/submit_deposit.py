from uuid import uuid4

from ....error_codes import (
    INSUFFICIENT_FUNDS,
    INVALID_AMOUNT,
    INVALID_PRECISION,
    UNSUPPORTED_ASSET,
    USER_NOT_FOUND,
)
from ....messaging import WalletTxMessage, WalletTxType
from ....ports import (
    ClockService,
    CurrencyQueryRepository,
    TransactionCommandRepository,
    UserQueryRepository,
    UserWalletCommandRepository,
)
from ....read_models import SubmittedTransactionSpec
from ....result import Result
from ....value_objects import Money
from ...sub_exec_base import SubmissionInterimHandlerResult
from .admin_deposit_cmd import AdminDepositCommand


class SubmitDepositHandler:
    def __init__(
        self,
        user_query_repo: UserQueryRepository,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        tx_command_repo: TransactionCommandRepository,
        clock_service: ClockService,
        admin_partition_key: str,
    ) -> None:
        self._user_query_repo = user_query_repo
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._tx_command_repo = tx_command_repo
        self._clock_service = clock_service
        self._admin_partition_key = admin_partition_key

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
        inserted = await self._tx_command_repo.insert_submitted(
            SubmittedTransactionSpec(
                id=uuid4(),
                request_id=request_id,
                type=WalletTxType.DEPOSIT,
                source_wallet_id=None,
                source_amount=money.amount,
                dest_wallet_id=wallet.id,
                dest_amount=money.amount,
                created_at=now,
                updated_at=now,
                reserve_source_debit=False,
            )
        )
        if not inserted:
            return Result.failure(INSUFFICIENT_FUNDS)
        return Result.success(
            SubmissionInterimHandlerResult(
                request_id=request_id,
                key=self._admin_partition_key,
                message=WalletTxMessage(
                    request_id=request_id,
                    msg_tx_type=WalletTxType.DEPOSIT,
                    submitted_at=now,
                ),
            )
        )
