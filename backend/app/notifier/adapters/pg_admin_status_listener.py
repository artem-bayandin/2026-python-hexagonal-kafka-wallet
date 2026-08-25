import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import asyncpg

from app.config import get_streaming_settings

from ..asyncpg_url import asyncpg_connect_kwargs
from ..ports import AdminStatusListener, AdminStatusWakeup


class _EventAdminStatusWakeup(AdminStatusWakeup):
    def __init__(self, event: asyncio.Event) -> None:
        self._event = event

    def clear(self) -> None:
        self._event.clear()

    async def wait(self, timeout_seconds: float) -> bool:
        if self._event.is_set():
            return True
        if timeout_seconds <= 0:
            return False
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return False
        return True


class PostgresAdminStatusListener(AdminStatusListener):
    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url
        self._channel = get_streaming_settings().transaction_status_channel

    def listen(self) -> AbstractAsyncContextManager[AdminStatusWakeup]:
        return self._listen()

    @asynccontextmanager
    async def _listen(self) -> AsyncIterator[AdminStatusWakeup]:
        connection = await asyncpg.connect(**asyncpg_connect_kwargs(self._database_url))
        event = asyncio.Event()
        listener_registered = False

        def _on_notify(
            _connection: object,
            _pid: int,
            _channel: str,
            _payload: object,
        ) -> None:
            event.set()

        try:
            await connection.add_listener(self._channel, _on_notify)
            listener_registered = True
            yield _EventAdminStatusWakeup(event)
        finally:
            try:
                if listener_registered and not connection.is_closed():
                    await connection.remove_listener(self._channel, _on_notify)
            finally:
                if not connection.is_closed():
                    await connection.close()
