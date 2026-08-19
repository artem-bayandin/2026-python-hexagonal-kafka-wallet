from typing import Annotated

from fastapi import APIRouter, Depends

from app.domain import CurrenciesQuery, UsersQuery

from ..dependencies import require_admin_or_user_auth
from ..executors import (
    ListCurrenciesExecutorFn,
    ListUsersExecutorFn,
    get_list_currencies_executor_fn,
    get_list_users_executor_fn,
)
from ..result_mapping import unwrap_domain_result
from ..schemas import (
    CurrencyItemResponse,
    DataList,
    UserReferenceItemResponse,
)

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get(
    "/currencies",
    dependencies=[Depends(require_admin_or_user_auth)],
)
async def list_currencies(
    executor_fn: Annotated[ListCurrenciesExecutorFn, Depends(get_list_currencies_executor_fn)],
) -> DataList[CurrencyItemResponse]:
    result = await executor_fn(CurrenciesQuery())
    data = unwrap_domain_result(result)
    return DataList(
        items=[
            CurrencyItemResponse(
                label=item.label,
                name=item.name,
                type=item.type,
                precision=item.precision,
            )
            for item in data
        ]
    )


@router.get(
    "/users",
    dependencies=[Depends(require_admin_or_user_auth)],
)
async def list_users(
    executor_fn: Annotated[ListUsersExecutorFn, Depends(get_list_users_executor_fn)],
) -> DataList[UserReferenceItemResponse]:
    result = await executor_fn(UsersQuery())
    data = unwrap_domain_result(result)
    return DataList(
        items=[UserReferenceItemResponse(user_id=item.user_id, email=item.email) for item in data]
    )
