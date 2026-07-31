from typing import Annotated

from fastapi import APIRouter, Depends

from app.domain import CurrenciesQuery, UsersQuery

from ..dependencies import (
    ListCurrenciesExecutor,
    ListUsersExecutor,
    get_list_currencies_executor,
    get_list_users_executor,
    require_admin_or_user_auth,
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
    executor: Annotated[ListCurrenciesExecutor, Depends(get_list_currencies_executor)],
) -> DataList[CurrencyItemResponse]:
    items = unwrap_domain_result(await executor(CurrenciesQuery()))
    return DataList(
        items=[
            CurrencyItemResponse(
                label=item.label,
                name=item.name,
                type=item.type,
                precision=item.precision,
            )
            for item in items
        ]
    )


@router.get(
    "/users",
    dependencies=[Depends(require_admin_or_user_auth)],
)
async def list_users(
    executor: Annotated[ListUsersExecutor, Depends(get_list_users_executor)],
) -> DataList[UserReferenceItemResponse]:
    items = unwrap_domain_result(await executor(UsersQuery()))
    return DataList(
        items=[UserReferenceItemResponse(user_id=item.user_id, email=item.email) for item in items]
    )
