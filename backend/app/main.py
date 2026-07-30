from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.api import (
    ApiResultError,
    handle_api_result_error,
    handle_uncaught_exception,
    handle_validation_error,
    auth_router,
    health_router,
    reference_router,
)
from app.config import Settings, get_settings
from app.db import build_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    engine: AsyncEngine = create_async_engine(resolved.database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Before yield = startup (nothing here yet; engine is already created above)
        yield
        # After yield = shutdown (runs when uvicorn stops or reloads)
        await engine.dispose()

    app = FastAPI(title="Wallet Sample", lifespan=lifespan)
    app.state.settings = resolved
    app.state.session_factory = session_factory

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

    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(ApiResultError, handle_api_result_error)
    app.add_exception_handler(Exception, handle_uncaught_exception)

    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(reference_router)

    @app.get("/health/ready")
    async def health_ready(response: Response) -> dict[str, str]:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            response.status_code = 503
            return {"status": "unavailable"}
        return {"status": "ok"}

    return app
