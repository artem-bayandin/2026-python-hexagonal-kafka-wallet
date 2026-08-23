import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from app.config import StreamingSettings
from app.notifier import StatusNotifier, TransactionStatusEvent

from ..dependencies import bind_current_user
from ..current_user_provider import get_current_user_provider
from ..sse_status_encoder import SseStatusEncoder

router = APIRouter(prefix="/me", tags=["stream"])


@router.get("/stream", dependencies=[Depends(bind_current_user)])
async def stream_transaction_status(
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    notifier: StatusNotifier = request.app.state.status_notifier
    streaming: StreamingSettings = request.app.state.streaming_settings
    user_id = get_current_user_provider().get().id
    after = SseStatusEncoder.decode_status_event_id(last_event_id)
    heartbeat_seconds = streaming.sse_heartbeat_interval_seconds
    retry_milliseconds = streaming.sse_retry_milliseconds

    async def event_stream() -> AsyncIterator[str]:
        yield f"retry: {retry_milliseconds}\n\n"
        iterator = notifier.subscribe(user_id, after)
        aiter = iterator.__aiter__()

        async def pull_event() -> TransactionStatusEvent:
            return await aiter.__anext__()

        nxt: asyncio.Task[TransactionStatusEvent] = asyncio.create_task(pull_event())
        try:
            while True:
                done, _pending = await asyncio.wait({nxt}, timeout=heartbeat_seconds)
                if not done:
                    yield ": keep-alive\n\n"
                    continue
                try:
                    event = nxt.result()
                except StopAsyncIteration:
                    break
                yield SseStatusEncoder.format_status_sse_event(event)
                nxt = asyncio.create_task(pull_event())
        finally:
            nxt.cancel()
            with suppress(asyncio.CancelledError):
                await nxt
            aclose = getattr(aiter, "aclose", None)
            if aclose is not None:
                await aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
