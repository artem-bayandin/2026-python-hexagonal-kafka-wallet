"""Bounded delay before re-checking a still-``submitted`` transaction."""

import asyncio

from app.config import WorkerSettings


async def await_submitted_visibility_delay(worker: WorkerSettings) -> None:
    await asyncio.sleep(worker.submitted_visibility_delay_ms / 1000)
