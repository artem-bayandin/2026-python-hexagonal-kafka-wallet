import asyncio
from collections.abc import Awaitable, Callable

from fastapi import Request

from app.dependencies import build_list_admin_transactions_handler
from app.domain import AdminTransactionsQuery, Result, TransactionListItem
from app.notifier import AdminStatusWakeup

from ..db_session import read_session

ListAdminTransactionsExecutorFn = Callable[
    [AdminTransactionsQuery, int], Awaitable[Result[list[TransactionListItem]]]
]

_DISCONNECT_CHECK_INTERVAL_SECONDS = 0.25


def get_list_admin_transactions_executor_fn(request: Request) -> ListAdminTransactionsExecutorFn:
    async def query_once(query: AdminTransactionsQuery) -> Result[list[TransactionListItem]]:
        async with read_session(request) as session:
            handler = build_list_admin_transactions_handler(session)
            return await handler.handle(query)

    async def execute_fn(
        query: AdminTransactionsQuery,
        timeout_seconds: int,
    ) -> Result[list[TransactionListItem]]:
        if query.after is None or timeout_seconds == 0:
            return await query_once(query)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        listener = request.app.state.admin_status_listener

        async with listener.listen() as wakeup:
            result = await query_once(query)
            if _should_return(result):
                return result

            while True:
                wakeup.clear()
                result = await query_once(query)
                if _should_return(result):
                    return result

                remaining_seconds = deadline - loop.time()
                if remaining_seconds <= 0:
                    return await query_once(query)

                was_notified = await _wait_for_wakeup_or_disconnect(
                    request,
                    wakeup,
                    remaining_seconds,
                )
                if not was_notified:
                    return await query_once(query)

                result = await query_once(query)
                if _should_return(result):
                    return result

    return execute_fn


def _should_return(result: Result[list[TransactionListItem]]) -> bool:
    return not result.is_success or bool(result.data)


async def _wait_for_wakeup_or_disconnect(
    request: Request,
    wakeup: AdminStatusWakeup,
    timeout_seconds: float,
) -> bool:
    wakeup_task = asyncio.create_task(wakeup.wait(timeout_seconds))
    disconnect_task = asyncio.create_task(_watch_for_disconnect(request))
    tasks = {wakeup_task, disconnect_task}
    try:
        done, pending = await asyncio.wait(
            tasks,
            timeout=timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    if disconnect_task in done:
        disconnected = disconnect_task.result()
        if wakeup_task in done:
            await asyncio.gather(wakeup_task, return_exceptions=True)
        if disconnected:
            return False
    if wakeup_task in done:
        return wakeup_task.result()
    return False


async def _watch_for_disconnect(request: Request) -> bool:
    while True:
        if await request.is_disconnected():
            return True
        await asyncio.sleep(_DISCONNECT_CHECK_INTERVAL_SECONDS)
