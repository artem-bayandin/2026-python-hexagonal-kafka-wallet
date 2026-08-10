from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.api import (
    DomainResultError,
    handle_domain_result_error,
    handle_uncaught_exception,
    handle_api_validation_error,
    admin_router,
    auth_router,
    health_router,
    reference_router,
    wallet_router,
)
from app.config import ApiSettings, load_api_runtime
from app.db import build_session_factory
from app.kafka.messaging import build_aiokafka_producer
from app.kafka.runtime import managed_kafka_producer


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    runtime = load_api_runtime()
    resolved = settings or runtime.api
    engine: AsyncEngine = create_async_engine(resolved.database_url)
    session_factory = build_session_factory(engine)
    kafka_producer = build_aiokafka_producer(runtime.kafka)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with managed_kafka_producer(kafka_producer):
            yield
        await engine.dispose()

    app = FastAPI(title="Wallet Sample", lifespan=lifespan)
    app.state.settings = resolved
    app.state.session_factory = session_factory
    app.state.engine = engine
    app.state.kafka_producer = kafka_producer
    app.state.kafka_settings = runtime.kafka

    cors_origins = [
        origin.strip() for origin in resolved.cors_allowed_origins.split(",") if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(RequestValidationError, handle_api_validation_error)
    app.add_exception_handler(DomainResultError, handle_domain_result_error)
    app.add_exception_handler(Exception, handle_uncaught_exception)

    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(reference_router)
    app.include_router(admin_router)
    app.include_router(wallet_router)

    return app
