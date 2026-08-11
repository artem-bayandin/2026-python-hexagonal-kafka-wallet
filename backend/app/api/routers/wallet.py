from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.domain import (
    ExchangeCommand,
    UserBalancesQuery,
    UserTransactionsQuery,
    PaginationParams,
    TransferCommand,
    WithdrawCommand,
)

from ..dependencies import (
    ExchangeExecutor,
    GetUserBalancesExecutor,
    ListUserTransactionsExecutor,
    TransferExecutor,
    WithdrawExecutor,
    bind_current_user,
    get_exchange_executor,
    get_get_user_balances_executor,
    get_list_user_transactions_executor,
    get_transfer_executor,
    get_withdraw_executor,
)
from ..formatting import format_amount_with_precision, map_not_null_asset_precision
from ..result_mapping import unwrap_domain_result
from ..schemas import (
    BalanceItemResponse,
    BalanceListResponse,
    ExchangeRequest,
    TransactionItemResponse,
    TransactionListResponse,
    TransferRequest,
    WalletMutationResponse,
    WithdrawRequest,
)

router = APIRouter(prefix="/me", tags=["wallet"])


@router.get(
    "/balances",
    dependencies=[Depends(bind_current_user)],
)
async def get_user_balances(
    balances_executor: Annotated[GetUserBalancesExecutor, Depends(get_get_user_balances_executor)],
) -> BalanceListResponse:
    items = unwrap_domain_result(await balances_executor(UserBalancesQuery()))
    return BalanceListResponse(
        items=[
            BalanceItemResponse(
                asset=item.asset,
                amount=format_amount_with_precision(item.amount, item.precision),
                locked=format_amount_with_precision(item.locked, item.precision),
            )
            for item in items
        ]
    )


@router.get(
    "/transactions",
    dependencies=[Depends(bind_current_user)],
)
async def list_user_transactions(
    executor: Annotated[
        ListUserTransactionsExecutor,
        Depends(get_list_user_transactions_executor),
    ],
    page_number: Annotated[int, Query(ge=0)] = 0,
    page_size: Annotated[int, Query(gt=0, le=100)] = 20,
) -> TransactionListResponse:
    page = unwrap_domain_result(
        await executor(
            UserTransactionsQuery(PaginationParams(page_number=page_number, page_size=page_size))
        )
    )
    return TransactionListResponse(
        total_items=page.total_items,
        items=[
            TransactionItemResponse(
                id=item.id,
                request_id=item.request_id,
                type=item.type,
                status=item.status.value,
                source_asset=item.source_asset,
                dest_asset=item.dest_asset,
                amount=format_amount_with_precision(
                    item.amount,
                    map_not_null_asset_precision(
                        item.source_asset,
                        item.dest_asset,
                        item.source_precision,
                        item.dest_precision,
                    ),
                ),
                error=item.error,
                created_at=item.created_at,
                updated_at=item.updated_at,
                direction=item.direction,
            )
            for item in page.items
        ],
    )


@router.post(
    "/exchanges",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(bind_current_user)],
)
async def create_exchange(
    body: ExchangeRequest,
    executor: Annotated[ExchangeExecutor, Depends(get_exchange_executor)],
) -> WalletMutationResponse:
    # Version 1 compatibility — replaced in Phase 3
    data = unwrap_domain_result(
        await executor(
            ExchangeCommand(
                source_asset_label=body.source_asset,
                destination_asset_label=body.destination_asset,
                amount_str=body.amount,
            )
        )
    )
    return WalletMutationResponse(id=data.transaction_id, type="EXCHANGE")


@router.post(
    "/withdrawals",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(bind_current_user)],
)
async def create_withdrawal(
    body: WithdrawRequest,
    executor: Annotated[WithdrawExecutor, Depends(get_withdraw_executor)],
) -> WalletMutationResponse:
    # Version 1 compatibility — replaced in Phase 3
    data = unwrap_domain_result(
        await executor(WithdrawCommand(asset_label=body.asset, amount_str=body.amount))
    )
    return WalletMutationResponse(id=data.transaction_id, type="WITHDRAWAL")


@router.post(
    "/transfers",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(bind_current_user)],
)
async def create_transfer(
    body: TransferRequest,
    executor: Annotated[TransferExecutor, Depends(get_transfer_executor)],
) -> WalletMutationResponse:
    # Version 1 compatibility — replaced in Phase 3
    data = unwrap_domain_result(
        await executor(
            TransferCommand(
                recipient_email=str(body.email),
                asset_label=body.asset,
                amount_str=body.amount,
            )
        )
    )
    return WalletMutationResponse(id=data.transaction_id, type="TRANSFER")
