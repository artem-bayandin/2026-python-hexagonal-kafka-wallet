from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text, update

from app.domain import (
    SubmittedTransactionSpec,
    TransactionCommandRepository,
    TransactionItem,
    TransactionStatus,
)
from app.config import get_streaming_settings

from ..mappers import TransactionDbMapper
from ..models import TransactionModel, UserWalletModel
from ..session import AsyncSession
from .user_wallet_command_repository import UserWalletCommandRepositoryImpl


class TransactionCommandRepositoryImpl(TransactionCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, transaction: TransactionItem) -> None:
        self.session.add(TransactionDbMapper.to_model(transaction))

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

    async def update_for_execution(self, request_id: UUID) -> TransactionItem | None:
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
        await self._notify_visible_users(model)
        return TransactionDbMapper.to_domain(model)

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
        await self._notify_visible_users(model)
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
        return TransactionDbMapper.to_domain(model)

    async def _notify_visible_users(self, model: TransactionModel) -> None:
        wallet_ids = [
            wallet_id
            for wallet_id in (model.source_wallet_id, model.dest_wallet_id)
            if wallet_id is not None
        ]
        if not wallet_ids:
            return
        user_ids = (
            (
                await self.session.execute(
                    select(UserWalletModel.user_id)
                    .where(UserWalletModel.id.in_(wallet_ids))
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        for user_id in user_ids:
            await self.session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {
                    "channel": get_streaming_settings().transaction_status_channel,
                    "payload": str(user_id),
                },
            )
