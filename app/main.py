from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    engine: AsyncEngine = create_async_engine(resolved.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Before yield = startup (nothing here yet; engine is already created above)
        yield
        # After yield = shutdown (runs when uvicorn stops or reloads)
        await engine.dispose()

    app = FastAPI(title="Wallet Sample", lifespan=lifespan)

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

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
