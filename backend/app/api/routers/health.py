from fastapi import APIRouter, Depends, Request, Response

from app.kafka.runtime import (
    ReadinessError,
    check_kafka_topics,
    check_postgres,
    check_schema_revision,
)

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


@router.get("/ready")
async def health_ready(request: Request, response: Response) -> dict[str, str]:
    engine = request.app.state.engine
    producer = request.app.state.kafka_producer
    kafka = request.app.state.kafka_settings
    try:
        await check_postgres(engine)
        await check_schema_revision(engine)
        await check_kafka_topics(producer, kafka)
    except ReadinessError:
        response.status_code = 503
        return {"status": "unavailable"}
    return {"status": "ok"}
