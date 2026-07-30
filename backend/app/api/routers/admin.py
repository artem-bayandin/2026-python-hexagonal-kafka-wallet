from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.domain import (
    AdminDepositCommand,
    GetAdminBalancesQuery,
    ListAdminTransactionsQuery,
    ListCurrenciesQuery,
    PaginationParams,
)

from ..dependencies import (
    AdminDepositExecutor,
    GetAdminBalancesExecutor,
    ListAdminTransactionsExecutor,
    ListCurrenciesExecutor,
    get_admin_deposit_executor,
    get_get_admin_balances_executor,
    get_list_admin_transactions_executor,
    get_list_currencies_executor,
    require_admin_key,
)
from ..formatting import format_amount
from ..result_mapping import unwrap_result
from ..schemas.admin import AdminDepositRequest, AdminDepositResponse
from ..schemas.wallet import (
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
    result = await executor(
        AdminDepositCommand(
            email=str(body.email),
            asset_label=body.asset,
            amount_str=body.amount,
        )
    )
    data = unwrap_result(result)
    return AdminDepositResponse(id=data.transaction_id)


@router.get(
    "/balances",
    dependencies=[Depends(require_admin_key)],
)
async def get_admin_balances(
    balances_executor: Annotated[
        GetAdminBalancesExecutor, Depends(get_get_admin_balances_executor)
    ],
    currencies_executor: Annotated[ListCurrenciesExecutor, Depends(get_list_currencies_executor)],
) -> BalanceListResponse:
    items = unwrap_result(await balances_executor(GetAdminBalancesQuery()))
    currencies = unwrap_result(await currencies_executor(ListCurrenciesQuery()))
    precision_by_label = {item.label: item.precision for item in currencies}
    return BalanceListResponse(
        items=[
            BalanceItemResponse(
                asset=item.asset,
                available=format_amount(item.available, item.asset, precision_by_label),
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
    page = unwrap_result(
        await executor(
            ListAdminTransactionsQuery(
                PaginationParams(page_number=page_number, page_size=page_size)
            )
        )
    )
    return TransactionListResponse(
        total_items=page.total_items,
        items=[
            TransactionItemResponse(
                id=item.id,
                type=item.type.upper(),
                status=item.status.upper(),
                created_at=item.created_at,
            )
            for item in page.items
        ],
    )
