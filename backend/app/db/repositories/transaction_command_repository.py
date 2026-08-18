from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update

from app.domain import (
    SubmittedTransactionSpec,
    TransactionCommandRepository,
    TransactionItem,
    TransactionStatus,
)

from ..mappers import transaction_to_domain, transaction_to_model
from ..models import TransactionModel
from ..session import AsyncSession
from .user_wallet_command_repository import UserWalletCommandRepositoryImpl


class TransactionCommandRepositoryImpl(TransactionCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, transaction: TransactionItem) -> None:
        self.session.add(transaction_to_model(transaction))

    async def insert_submitted(self, spec: SubmittedTransactionSpec) -> bool:
        if spec.reserve_source_debit:
            if spec.source_wallet_id is None:
                raise ValueError("reserve_source_debit requires source_wallet_id")
            wallet_repo = UserWalletCommandRepositoryImpl(self.session)
            reserved = await wallet_repo.reserve_debit(
                spec.source_wallet_id,
                spec.source_amount,
                spec.updated_at,
            )
            if not reserved:
                return False

        self.session.add(
            TransactionModel(
                id=spec.id,
                request_id=spec.request_id,
                type=spec.type,
                source_wallet_id=spec.source_wallet_id,
                source_amount=spec.source_amount,
                dest_wallet_id=spec.dest_wallet_id,
                dest_amount=spec.dest_amount,
                status=TransactionStatus.SUBMITTED.value,
                error=None,
                created_at=spec.created_at,
                updated_at=spec.updated_at,
            )
        )
        return True

    async def mark_pending_if_submitted(self, request_id: UUID) -> int:
        return await self._guarded_status_update(
            request_id=request_id,
            expected=TransactionStatus.SUBMITTED,
            target=TransactionStatus.PENDING,
            safe_error=None,
            release_reservation=False,
        )

    async def fail_if_submitted(self, request_id: UUID, safe_error: str) -> int:
        return await self._guarded_status_update(
            request_id=request_id,
            expected=TransactionStatus.SUBMITTED,
            target=TransactionStatus.FAILED,
            safe_error=safe_error,
            release_reservation=True,
        )

    async def fail_if_pending(self, request_id: UUID, safe_error: str) -> int:
        return await self._guarded_status_update(
            request_id=request_id,
            expected=TransactionStatus.PENDING,
            target=TransactionStatus.FAILED,
            safe_error=safe_error,
            release_reservation=True,
        )

    async def claim_for_execution(self, request_id: UUID) -> TransactionItem | None:
        now = datetime.now(UTC)
        stmt = (
            update(TransactionModel)
            .where(
                TransactionModel.request_id == request_id,
                TransactionModel.status == TransactionStatus.PENDING.value,
            )
            .values(
                status=TransactionStatus.IN_PROGRESS.value,
                updated_at=now,
            )
            .returning(TransactionModel)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return transaction_to_domain(model)

    async def complete_if_in_progress(self, request_id: UUID, safe_error: str | None) -> int:
        target = TransactionStatus.SUCCEEDED if safe_error is None else TransactionStatus.FAILED
        return await self._guarded_status_update(
            request_id=request_id,
            expected=TransactionStatus.IN_PROGRESS,
            target=target,
            safe_error=safe_error,
            release_reservation=safe_error is not None,
        )

    async def _guarded_status_update(
        self,
        *,
        request_id: UUID,
        expected: TransactionStatus,
        target: TransactionStatus,
        safe_error: str | None,
        release_reservation: bool,
    ) -> int:
        lock_stmt = (
            select(TransactionModel)
            .where(TransactionModel.request_id == request_id)
            .with_for_update()
        )
        model = (await self.session.execute(lock_stmt)).scalar_one_or_none()
        if model is None or model.status != expected.value:
            return 0

        now = datetime.now(UTC)
        if release_reservation and model.source_wallet_id is not None:
            wallet_repo = UserWalletCommandRepositoryImpl(self.session)
            await wallet_repo.release_reservation(
                model.source_wallet_id,
                model.source_amount,
                now,
            )

        model.status = target.value
        model.updated_at = now
        model.error = safe_error
        await self.session.flush()
        return 1

    async def lock_by_request_id(self, request_id: UUID) -> TransactionItem | None:
        stmt = (
            select(TransactionModel)
            .where(TransactionModel.request_id == request_id)
            .with_for_update()
        )
        model = (await self.session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        return transaction_to_domain(model)
