from contextlib import AbstractAsyncContextManager
from typing import Protocol


class AdminStatusWakeup(Protocol):
    def clear(self) -> None: ...

    async def wait(self, timeout_seconds: float) -> bool: ...


class AdminStatusListener(Protocol):
    def listen(self) -> AbstractAsyncContextManager[AdminStatusWakeup]: ...
