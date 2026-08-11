from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.domain import (
    AdminDepositCommand,
    AdminBalancesQuery,
    AdminTransactionsQuery,
    PaginationParams,
)

from ..dependencies import (
    AdminDepositExecutor,
    GetAdminBalancesExecutor,
    ListAdminTransactionsExecutor,
    get_admin_deposit_executor,
    get_get_admin_balances_executor,
    get_list_admin_transactions_executor,
    require_admin_key,
)
from ..formatting import format_amount_with_precision, map_not_null_asset_precision
from ..result_mapping import unwrap_domain_result
from ..schemas import (
    AdminDepositRequest,
    AdminDepositResponse,
    BalanceItemResponse,
    BalanceListResponse,
    TransactionItemResponse,
    TransactionListResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/deposits",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
)
async def create_deposit(
    body: AdminDepositRequest,
    executor: Annotated[AdminDepositExecutor, Depends(get_admin_deposit_executor)],
) -> AdminDepositResponse:
    # Version 1 compatibility — replaced in Phase 3
    result = await executor(
        AdminDepositCommand(
            email=str(body.email),
            asset_label=body.asset,
            amount_str=body.amount,
        )
    )
    data = unwrap_domain_result(result)
    return AdminDepositResponse(id=data.transaction_id)


@router.get(
    "/balances",
    dependencies=[Depends(require_admin_key)],
)
async def get_admin_balances(
    balances_executor: Annotated[
        GetAdminBalancesExecutor, Depends(get_get_admin_balances_executor)
    ],
) -> BalanceListResponse:
    items = unwrap_domain_result(await balances_executor(AdminBalancesQuery()))
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
    dependencies=[Depends(require_admin_key)],
)
async def list_admin_transactions(
    executor: Annotated[
        ListAdminTransactionsExecutor,
        Depends(get_list_admin_transactions_executor),
    ],
    page_number: Annotated[int, Query(ge=0)] = 0,
    page_size: Annotated[int, Query(gt=0, le=100)] = 20,
) -> TransactionListResponse:
    page = unwrap_domain_result(
        await executor(
            AdminTransactionsQuery(PaginationParams(page_number=page_number, page_size=page_size))
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
            )
            for item in page.items
        ],
    )
