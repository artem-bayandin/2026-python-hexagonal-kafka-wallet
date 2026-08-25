"""Version 2 transaction lifecycle statuses and transition rules.

Shared implementation notes:

- **Terminal-state decision:** a worker observing ``succeeded``/``failed`` acknowledges
  and skips without any wallet mutation.
- **Duplicate-delivery decision:** a guarded conditional update affecting zero rows means
  another actor already advanced the row; reload and observe, never force a transition.
- **Stale-delivery decision:** a redelivery of ``in_progress`` after worker failure may
  resume execution under row locks; it is never permission to re-apply a committed mutation.
- **``submitted``-race decision:** a worker consuming a transaction still in ``submitted``
  must not treat it as a duplicate; it defers/retries safely until ``pending`` or a
  terminal state is visible (Kafka consumption can race the API's post-ack update).
"""

from enum import StrEnum


class TransactionStatus(StrEnum):
    SUBMITTED = "submitted"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


TERMINAL_STATUSES = frozenset({TransactionStatus.SUCCEEDED, TransactionStatus.FAILED})

ALLOWED_TRANSITIONS = frozenset(
    {
        (TransactionStatus.SUBMITTED, TransactionStatus.PENDING),
        (TransactionStatus.SUBMITTED, TransactionStatus.FAILED),
        (TransactionStatus.PENDING, TransactionStatus.IN_PROGRESS),
        (TransactionStatus.IN_PROGRESS, TransactionStatus.SUCCEEDED),
        (TransactionStatus.IN_PROGRESS, TransactionStatus.FAILED),
    }
)


def is_allowed_transition(current: TransactionStatus, target: TransactionStatus) -> bool:
    return (current, target) in ALLOWED_TRANSITIONS
