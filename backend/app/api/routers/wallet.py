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

from ..dependencies import bind_current_user
from ..executors import (
    ExchangeExecutorFn,
    GetUserBalancesExecutorFn,
    ListUserTransactionsExecutorFn,
    TransferExecutorFn,
    WithdrawExecutorFn,
    get_exchange_executor_fn,
    get_user_balances_executor_fn,
    get_list_user_transactions_executor_fn,
    get_transfer_executor_fn,
    get_withdraw_executor_fn,
)
from ..formatting import format_amount_with_precision, map_not_null_asset_precision
from ..result_mapping import unwrap_domain_result
from ..schemas import (
    BalanceItemResponse,
    BalanceListResponse,
    ExchangeRequest,
    SubmissionAcceptedResponse,
    TransactionItemResponse,
    TransactionListResponse,
    TransferRequest,
    WithdrawRequest,
)

router = APIRouter(prefix="/me", tags=["wallet"])


@router.get(
    "/balances",
    dependencies=[Depends(bind_current_user)],
)
async def get_user_balances(
    executor_fn: Annotated[GetUserBalancesExecutorFn, Depends(get_user_balances_executor_fn)],
) -> BalanceListResponse:
    result = await executor_fn(UserBalancesQuery())
    data = unwrap_domain_result(result)
    return BalanceListResponse(
        items=[
            BalanceItemResponse(
                asset=item.asset,
                amount=format_amount_with_precision(item.amount, item.precision),
                locked=format_amount_with_precision(item.locked, item.precision),
            )
            for item in data
        ]
    )


@router.get(
    "/transactions",
    dependencies=[Depends(bind_current_user)],
)
async def list_user_transactions(
    executor_fn: Annotated[
        ListUserTransactionsExecutorFn, Depends(get_list_user_transactions_executor_fn)
    ],
    page_number: Annotated[int, Query(ge=0)] = 0,
    page_size: Annotated[int, Query(gt=0, le=100)] = 20,
) -> TransactionListResponse:
    result = await executor_fn(
        UserTransactionsQuery(PaginationParams(page_number=page_number, page_size=page_size))
    )
    data = unwrap_domain_result(result)
    return TransactionListResponse(
        total_items=data.total_items,
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
            for item in data.items
        ],
    )


@router.post(
    "/exchanges",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(bind_current_user)],
)
async def create_exchange(
    body: ExchangeRequest,
    executor_fn: Annotated[ExchangeExecutorFn, Depends(get_exchange_executor_fn)],
) -> SubmissionAcceptedResponse:
    result = await executor_fn(
        ExchangeCommand(
            source_asset_label=body.source_asset,
            destination_asset_label=body.destination_asset,
            amount_str=body.amount,
        )
    )
    data = unwrap_domain_result(result)
    return SubmissionAcceptedResponse(request_id=data.request_id)


@router.post(
    "/withdrawals",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(bind_current_user)],
)
async def create_withdrawal(
    body: WithdrawRequest,
    executor_fn: Annotated[WithdrawExecutorFn, Depends(get_withdraw_executor_fn)],
) -> SubmissionAcceptedResponse:
    result = await executor_fn(WithdrawCommand(asset_label=body.asset, amount_str=body.amount))
    data = unwrap_domain_result(result)
    return SubmissionAcceptedResponse(request_id=data.request_id)


@router.post(
    "/transfers",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(bind_current_user)],
)
async def create_transfer(
    body: TransferRequest,
    executor_fn: Annotated[TransferExecutorFn, Depends(get_transfer_executor_fn)],
) -> SubmissionAcceptedResponse:
    result = await executor_fn(
        TransferCommand(
            recipient_email=str(body.email),
            asset_label=body.asset,
            amount_str=body.amount,
        )
    )
    data = unwrap_domain_result(result)
    return SubmissionAcceptedResponse(request_id=data.request_id)
