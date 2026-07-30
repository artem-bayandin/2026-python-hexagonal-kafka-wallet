from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.domain import AdminDepositCommand

from ..dependencies import (
    AdminDepositExecutor,
    get_admin_deposit_executor,
    require_admin_key,
)
from ..result_mapping import unwrap_result
from ..schemas.admin import AdminDepositRequest, AdminDepositResponse

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
