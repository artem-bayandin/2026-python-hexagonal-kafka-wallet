import asyncio
from collections.abc import AsyncIterator, Callable
from uuid import UUID

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_streaming_settings

from ..asyncpg_url import asyncpg_connect_kwargs
from ..ports import StatusEventRepository, StatusNotifier
from ..status_event import StatusCursor, TransactionStatusEvent


class PostgresStatusNotifier(StatusNotifier):
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        database_url: str,
        query_repository_factory: Callable[[AsyncSession], StatusEventRepository],
    ) -> None:
        streaming = get_streaming_settings()
        self._session_factory = session_factory
        self._database_url = database_url
        self._query_repository_factory = query_repository_factory
        self._page_size = streaming.status_event_page_size
        self._channel = streaming.transaction_status_channel

    def subscribe(
        self, user_id: UUID, after: StatusCursor | None
    ) -> AsyncIterator[TransactionStatusEvent]:
        return self._subscribe(user_id, after)

    async def _subscribe(
        self, user_id: UUID, after: StatusCursor | None
    ) -> AsyncIterator[TransactionStatusEvent]:
        connection = await asyncpg.connect(**asyncpg_connect_kwargs(self._database_url))
        wakeup = asyncio.Event()

        def _on_notify(_connection: object, _pid: int, _channel: str, payload: object) -> None:
            try:
                if UUID(str(payload)) == user_id:
                    wakeup.set()
            except ValueError:
                return

        try:
            await connection.add_listener(self._channel, _on_notify)
            cursor = after
            if cursor is not None:
                async for event in self._replay(user_id, cursor):
                    cursor = StatusCursor(event.updated_at, event.transaction_id)
                    yield event
            else:
                cursor = await self._high_water(user_id)

            while True:
                emitted = False
                async for event in self._replay(user_id, cursor):
                    cursor = StatusCursor(event.updated_at, event.transaction_id)
                    emitted = True
                    yield event
                if emitted:
                    continue
                wakeup.clear()
                async for event in self._replay(user_id, cursor):
                    cursor = StatusCursor(event.updated_at, event.transaction_id)
                    emitted = True
                    yield event
                if emitted:
                    continue
                await wakeup.wait()
        finally:
            await connection.remove_listener(self._channel, _on_notify)
            await connection.close()

    async def _high_water(self, user_id: UUID) -> StatusCursor | None:
        async with self._session_factory() as session:
            repository = self._query_repository_factory(session)
            return await repository.get_status_high_water(user_id)

    async def _replay(
        self, user_id: UUID, after: StatusCursor | None
    ) -> AsyncIterator[TransactionStatusEvent]:
        cursor = after
        while True:
            async with self._session_factory() as session:
                repository = self._query_repository_factory(session)
                page = await repository.list_status_events_after(user_id, cursor, self._page_size)
            if not page:
                return
            for event in page:
                cursor = StatusCursor(event.updated_at, event.transaction_id)
                yield event
            if len(page) < self._page_size:
                return
