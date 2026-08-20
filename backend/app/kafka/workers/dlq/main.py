import logging


logger = logging.getLogger(__name__)


async def run_dlq_worker() -> int:
    return 0


async def main() -> int:
    return await run_dlq_worker()
