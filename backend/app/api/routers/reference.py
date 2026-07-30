from typing import Annotated

from fastapi import APIRouter, Depends

from app.domain import ListCurrenciesQuery, ListUsersQuery

from ..dependencies import (
    ListCurrenciesExecutor,
    ListUsersExecutor,
    get_list_currencies_executor,
    get_list_users_executor,
    require_reference_auth,
)
from ..result_mapping import unwrap_result
from ..schemas import (
    CurrencyItemResponse,
    DataList,
    UserReferenceItemResponse,
)

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get(
    "/currencies",
    dependencies=[Depends(require_reference_auth)],
)
async def list_currencies(
    executor: Annotated[ListCurrenciesExecutor, Depends(get_list_currencies_executor)],
) -> DataList[CurrencyItemResponse]:
    items = unwrap_result(await executor(ListCurrenciesQuery()))
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
    dependencies=[Depends(require_reference_auth)],
)
async def list_users(
    executor: Annotated[ListUsersExecutor, Depends(get_list_users_executor)],
) -> DataList[UserReferenceItemResponse]:
    items = unwrap_result(await executor(ListUsersQuery()))
    return DataList(
        items=[UserReferenceItemResponse(user_id=item.user_id, email=item.email) for item in items]
    )
