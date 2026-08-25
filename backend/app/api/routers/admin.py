from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.exceptions import RequestValidationError

from app.domain import (
    AdminBalancesQuery,
    AdminDepositCommand,
    AdminTransactionCursor,
    AdminTransactionsQuery,
    TransactionListItem,
)

from ..admin_transaction_cursor_codec import AdminTransactionCursorCodec
from ..dependencies import require_admin_key
from ..executors import (
    AdminBalancesExecutorFn,
    AdminDepositExecutorFn,
    ListAdminTransactionsExecutorFn,
    get_admin_balances_executor_fn,
    get_admin_deposit_executor_fn,
    get_list_admin_transactions_executor_fn,
)
from ..formatting import format_amount_with_precision, map_not_null_asset_precision
from ..result_mapping import unwrap_domain_result
from ..schemas import (
    AdminDepositRequest,
    AdminTransactionPollResponse,
    BalanceItemResponse,
    BalanceListResponse,
    SubmissionAcceptedResponse,
    TransactionItemResponse,
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
    request: Request,
    executor_fn: Annotated[
        ListAdminTransactionsExecutorFn, Depends(get_list_admin_transactions_executor_fn)
    ],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    timeout_seconds: Annotated[int | None, Query(ge=0)] = None,
) -> AdminTransactionPollResponse:
    try:
        after = AdminTransactionCursorCodec.decode(cursor)
    except ValueError as error:
        raise _query_validation_error("cursor") from error

    streaming_settings = request.app.state.streaming_settings
    resolved_timeout_seconds = (
        streaming_settings.admin_long_poll_default_seconds
        if timeout_seconds is None
        else timeout_seconds
    )
    if resolved_timeout_seconds > streaming_settings.admin_long_poll_max_seconds:
        raise _query_validation_error("timeout_seconds")
    if after is None:
        resolved_timeout_seconds = 0

    result = await executor_fn(
        AdminTransactionsQuery(after=after, limit=limit),
        resolved_timeout_seconds,
    )
    data = unwrap_domain_result(result)
    next_cursor = _next_admin_transaction_cursor(data, after=after, input_cursor=cursor)
    return AdminTransactionPollResponse(
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
            for item in data
        ],
        next_cursor=next_cursor,
    )


def _next_admin_transaction_cursor(
    items: list[TransactionListItem],
    *,
    after: AdminTransactionCursor | None,
    input_cursor: str | None,
) -> str | None:
    if not items:
        return input_cursor if after is not None else None
    last_item = items[-1]
    return AdminTransactionCursorCodec.encode(
        AdminTransactionCursor(
            updated_at=last_item.updated_at,
            transaction_id=last_item.id,
        )
    )


def _query_validation_error(field: str) -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": ("query", field),
                "msg": "Invalid query parameter.",
            }
        ]
    )
