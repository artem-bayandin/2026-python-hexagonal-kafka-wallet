from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def _db_session(request: Request, *, transactional: bool) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        if transactional:
            async with session.begin():
                yield session
        else:
            yield session


@asynccontextmanager
async def read_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with _db_session(request, transactional=False) as session:
        yield session


@asynccontextmanager
async def write_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with _db_session(request, transactional=True) as session:
        yield session


__all__ = [
    "read_session",
    "write_session",
]
