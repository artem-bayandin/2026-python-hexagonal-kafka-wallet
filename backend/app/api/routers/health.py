from fastapi import APIRouter, Depends

from ..dependencies import bind_current_user

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "/authenticated",
    dependencies=[Depends(bind_current_user)],
)
async def health_authenticated() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}

# @router.get("/ready")
# lives in main.py as it requires a direct db conneciton

