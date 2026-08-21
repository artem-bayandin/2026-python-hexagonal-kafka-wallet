# Phase 3A — Refactoring log

Post-Phase-3 improvements. Canonical env contract remains [CONFIGURATION.md](../v2/CONFIGURATION.md). This file records what changed in that contract so later refactor notes can accumulate here.

## Kafka retry mapping (aiokafka 0.14)

Producer inner retries are time-based (`request_timeout_ms` + `retry_backoff_ms`). Idempotence stays on; the app bounds `send_and_wait` with `KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS`. Worker execution is one attempt per delivery (no local attempt loop). Offsets stay manual (`enable_auto_commit=false`). Full behavior: [kafka_retry_upd.md](../../kafka_retry_upd.md).

### Producer reliability ([CONFIGURATION.md](../v2/CONFIGURATION.md) §5)

Kept:

| Variable | Default | Role |
| --- | --- | --- |
| `KAFKA_PRODUCER_REQUEST_TIMEOUT_MS` | `10000` | Broker Produce RPC timeout; also passed to the consumer as request timeout. |
| `KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS` | `30000` | End-to-end `asyncio.wait_for` around one `send_and_wait`; must be ≥ request timeout. |
| `KAFKA_PRODUCER_RETRY_BACKOFF_MS` | `200` | Fixed delay between aiokafka inner produce (and consumer fetch) retries. |

Removed:

- `KAFKA_PRODUCER_MAX_RETRIES` — aiokafka has no attempt-count setting.
- `KAFKA_PRODUCER_RETRY_BACKOFF_MAX_MS` — inner backoff is fixed, not exponential.

Unchanged guarantees: `acks=all`, `enable_idempotence=true`. Idempotent mode does not expire batches on the request timeout, so the delivery bound is required.

### Worker consumption and execution ([CONFIGURATION.md](../v2/CONFIGURATION.md) §6)

Kept:

| Variable | Default | Role |
| --- | --- | --- |
| `WORKER_RETRY_BACKOFF_MS` | `500` | Submitted-row visibility wait only (not an execution retry schedule). |
| `WORKER_POLL_TIMEOUT_MS` | `1000` | Poll wait. |
| `WORKER_HEARTBEAT_INTERVAL_MS` | `3000` | Heartbeat; must be below session timeout. |
| `WORKER_SESSION_TIMEOUT_MS` | `30000` | Group session timeout. |
| `WORKER_MAX_POLL_INTERVAL_MS` | `300000` | Must cover polling plus the bounded DLQ publication wait. |

Removed:

- `WORKER_MAX_ATTEMPTS` — one `handler.execute` per delivery; retryable infra failure uses the same terminal DB + DLQ + ACK path as poison.
- `WORKER_RETRY_BACKOFF_MAX_MS` — no in-process exponential retry schedule.

### Validation invariants ([CONFIGURATION.md](../v2/CONFIGURATION.md) §14)

- Producer: `acks=all`, idempotence on, inner retries use `KAFKA_PRODUCER_RETRY_BACKOFF_MS`, delivery timeout ≥ request timeout.
- Worker: heartbeat below session timeout; `WORKER_MAX_POLL_INTERVAL_MS` covers poll + DLQ publication wait (no local retry-schedule term).
