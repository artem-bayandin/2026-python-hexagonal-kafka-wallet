from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.domain import (
    AdminDepositCommand,
    AdminBalancesQuery,
    AdminTransactionsQuery,
    PaginationParams,
)

from ..executors import (
    AdminDepositExecutorFn,
    AdminBalancesExecutorFn,
    ListAdminTransactionsExecutorFn,
    get_admin_deposit_executor_fn,
    get_admin_balances_executor_fn,
    get_list_admin_transactions_executor_fn,
)
from ..dependencies import require_admin_key
from ..formatting import format_amount_with_precision, map_not_null_asset_precision
from ..result_mapping import unwrap_domain_result
from ..schemas import (
    AdminDepositRequest,
    BalanceItemResponse,
    BalanceListResponse,
    SubmissionAcceptedResponse,
    TransactionItemResponse,
    TransactionListResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/deposits",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin_key)],
)
async def create_deposit(
    body: AdminDepositRequest,
    executor_fn: Annotated[AdminDepositExecutorFn, Depends(get_admin_deposit_executor_fn)],
) -> SubmissionAcceptedResponse:
    result = await executor_fn(
        AdminDepositCommand(
            email=str(body.email),
            asset_label=body.asset,
            amount_str=body.amount,
        )
    )
    data = unwrap_domain_result(result)
    return SubmissionAcceptedResponse(request_id=data.request_id)


@router.get(
    "/balances",
    dependencies=[Depends(require_admin_key)],
)
async def get_admin_balances(
    executor_fn: Annotated[AdminBalancesExecutorFn, Depends(get_admin_balances_executor_fn)],
) -> BalanceListResponse:
    result = await executor_fn(AdminBalancesQuery())
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
    dependencies=[Depends(require_admin_key)],
)
async def list_admin_transactions(
    executor_fn: Annotated[
        ListAdminTransactionsExecutorFn, Depends(get_list_admin_transactions_executor_fn)
    ],
    page_number: Annotated[int, Query(ge=0)] = 0,
    page_size: Annotated[int, Query(gt=0, le=100)] = 20,
) -> TransactionListResponse:
    result = await executor_fn(
        AdminTransactionsQuery(PaginationParams(page_number=page_number, page_size=page_size))
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
            )
            for item in data.items
        ],
    )
