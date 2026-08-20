import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.config import WorkerSettings
from app.domain import PoisonExecutionError, RetryableExecutionError

logger = logging.getLogger(__name__)


async def run_with_retries[T](
    worker: WorkerSettings,
    *,
    request_id: str,
    operation: Callable[[], Awaitable[T]],
) -> T:
    backoff_ms = worker.retry_backoff_ms
    last_error: Exception | None = None
    for attempt in range(1, worker.max_attempts + 1):
        try:
            return await operation()
        except PoisonExecutionError:
            raise
        except RetryableExecutionError as error:
            last_error = error
            if attempt == worker.max_attempts:
                break
            logger.warning(
                "worker retry scheduled",
                extra={
                    "request_id": request_id,
                    "attempt": str(attempt),
                    "backoff_ms": str(backoff_ms),
                },
            )
            await asyncio.sleep(backoff_ms / 1000)
            backoff_ms = min(backoff_ms * 2, worker.retry_backoff_max_ms)
        except Exception as error:
            if _is_retryable_infrastructure_error(error):
                last_error = RetryableExecutionError(str(error))
                if attempt == worker.max_attempts:
                    break
                logger.warning(
                    "worker retry scheduled",
                    extra={
                        "request_id": request_id,
                        "attempt": str(attempt),
                        "backoff_ms": str(backoff_ms),
                        "error_type": type(error).__name__,
                    },
                )
                await asyncio.sleep(backoff_ms / 1000)
                backoff_ms = min(backoff_ms * 2, worker.retry_backoff_max_ms)
            else:
                raise PoisonExecutionError(str(error)) from error
    assert last_error is not None
    raise last_error


def _is_retryable_infrastructure_error(error: Exception) -> bool:
    module_name = type(error).__module__
    if module_name.startswith("sqlalchemy") or module_name.startswith("asyncpg"):
        return True
    if module_name.startswith("aiokafka"):
        return bool(getattr(error, "retriable", False))
    return False
