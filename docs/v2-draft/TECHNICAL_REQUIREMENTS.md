# Clean Architecture Wallet — Technical Requirements

### 2.3 Version 2 messaging

- Apache Kafka 4.3
- `aiokafka>=0.14,<0.15` as the async Python Kafka client
- Transactional outbox and duplicate-safe inbox/message processing
- One wallet command topic partitioned by target user ID
- One command worker process with deposit, exchange, and withdrawal handlers

Kafka and the worker are introduced only in version 2.

- Version 2 extends Docker Compose with Kafka and the command worker.
- Configuration, profile boundaries, local ports, topic names, and polling defaults are defined in [CONFIGURATION.md](CONFIGURATION.md).

- The current baseline is Python 3.14.6, FastAPI 0.139.2, Pydantic 2.13.4, `pydantic-settings` 2.14.2, SQLAlchemy 2.0.51, `uv` 0.11.31, `testcontainers` 4.14.2, `email-validator` 2.3.0, and `aiokafka` 0.14.0.
- Apache Kafka 4.3.1 is the broker baseline. Pin its image to an exact patch tag or immutable digest.

- incoming adapters translate HTTP or Kafka messages into commands/queries;
- outgoing ports describe persistence, token, OTP, clock, and messaging needs;
- PostgreSQL, FastAPI, PyJWT, and Kafka are outer adapters;

`domain/` must not import FastAPI, Pydantic, SQLAlchemy, PyJWT, or Kafka packages.

```
api / kafka worker ──> domain commands and queries <── ports
db / auth / messaging adapters ──────────────────────> ports
```

│   │   ├── messaging/                 # version 2
│   │   │   ├── contracts.py
│   │   │   ├── kafka_adapter.py
│   │   │   ├── outbox_relay.py
│   │   │   └── worker.py
│   │   └── kafka_api/                 # version 2, removable diagnostics adapter
│   │       ├── router.py
│   │       ├── schemas.py
│   │       ├── service.py
│   │       └── repository.py

- Version 2 may add balance buckets or equivalent columns — strategy TBD when Kafka work starts ([PHASE_6_KAFKA.md](implementation/PHASE_6_KAFKA.md)).

- version 2: additional statuses such as `pending`, `rejected`.

Version 2 separates submission from execution for wallet mutations:

- HTTP submission handlers create a pending transaction and outbox command;
- deposit submission also increments the pending balance;
- worker execution handlers perform current-state validation and balance transitions;
- worker handlers finalize transaction and message state with guarded duplicate-safe transitions.

- operation status;
- Kafka diagnostics messages through the isolated diagnostics module.

Unexpected infrastructure and programming failures are not converted to `Result.failure`. They propagate as exceptions so the active transaction rolls back and the API or worker can apply its unexpected-failure policy.

Use one async SQLAlchemy session per HTTP command or consumed Kafka message:

The session dependency, command executor, or worker message scope supplies the transaction boundary.

Version 2 adds:

- outbox messages;
- inbox/processed messages;
- Kafka message diagnostics records, or equivalent operational columns that support the diagnostics queries.

- The OTP is returned only when `APP_ENV=development` and `ENABLE_DEMO_OTP=true`; it must not appear in logs or Kafka diagnostics.

Only authenticated HTTP use cases use this provider. OTP request/verification, development admin operations, Kafka workers, and other non-request execution paths receive identity explicitly from their own inputs when needed. Do not let detached/background tasks depend on the request provider because Python task creation can copy `ContextVar` state; pass any required identity explicitly instead.

### 7.5 Kafka diagnostics

`/kafka/*` diagnostics endpoints require no authentication only when `APP_ENV=development` and `ENABLE_KAFKA_DIAGNOSTICS=true`. They return `404` otherwise. Their payloads must exclude OTPs, JWTs, admin keys, connection strings, and secrets. The module is development-only and removable.

- `GET /me/operations/{operation_id}` in version 2

- `GET /admin/operations/{operation_id}` in version 2

### 8.5 Kafka diagnostics

- `GET /kafka/messages`
- `GET /kafka/messages/{message_id}`

Success status codes remain route-specific (`200`, `201`, `202`, or `204`) and are not selected by `unwrap_domain_result`. Request-validation failures bypass `Result[T]` and remain `422 VALIDATION_ERROR`; uncaught exceptions remain `500 INTERNAL_ERROR`.

Version 1 wallet commands return completed results. Version 2 deposit, exchange, and withdrawal submissions return `202 Accepted` and an operation identifier. HTTP idempotency keys are deferred to the roadmap's final optional hardening phase.

## 9. Version 2 messaging

### 9.1 Command envelope

Each command is published to the `wallet.commands.v1` topic and consumed by the `wallet-command-worker-v1` consumer group. Each Kafka command contains:

- schema version;
- unique message ID;
- operation/transaction ID;
- command type;
- target user ID used as partition key;
- causation/correlation IDs;
- creation timestamp;
- typed payload.

Contracts are versioned DTOs and contain no ORM or Pydantic API objects.

### 9.2 Outbox

HTTP submission writes the operation and outbox row atomically. A relay claims unpublished rows, publishes them, and records publication metadata.

Database commit and Kafka publish cannot form one transaction, so delivery is at least once. Inbox uniqueness and guarded state transitions must prevent duplicate application; the system must not claim exactly-once end-to-end behavior.

### 9.3 Worker

- One consumer group processes wallet commands.
- Messages are keyed by target user ID for per-user ordering.
- One worker dispatches to deposit, exchange, and withdrawal execution handlers.
- The worker records processing state before/following execution.
- A duplicate message returns the previously recorded outcome without applying balances again.
- Business rejection and infrastructure failure are distinct states.
- Infrastructure failures remain retryable and do not become AML rejection.

### 9.4 Kafka diagnostics module

`app/kafka_api/` owns only the diagnostics HTTP/query boundary:

- router;
- request/response schemas;
- query service;
- read repository.

It queries PostgreSQL message records, not Kafka directly. Core wallet domain and command handlers do not import this package. Registration in `main.py` is the only application-level dependency, allowing later removal.

The frontend contains Login, Wallet (including paginated history), Admin, and version-2 Kafka views. Version 1 switches views with React state in `App.tsx`; URL routing is optional future work.

- Admin and Kafka views are development-only; production builds must omit those views until production authorization and observability controls exist.
- Version 2 polls operation, balance, transaction, and diagnostics queries using the bounded exponential-backoff defaults in [CONFIGURATION.md](CONFIGURATION.md); WebSockets are not required.
- Error responses and pending/rejected/failed statuses are visible in simple text UI.

Worker business failures returned through `Result.failure` become `REJECTED` outcomes with safe reason codes. Unexpected exceptions become `FAILED`, are logged safely, and remain eligible for retry.

- Version 2 state transitions and duplicate-message handling.
- No FastAPI, SQLAlchemy, PostgreSQL, or Kafka is needed.

- Version-2 outbox publication and worker processing.
- Per-user ordering, duplicate delivery, rejection, retry, and failure cases.
- Kafka diagnostics API projections and secret sanitization.

- rendering pending/completed/rejected states;
- Kafka diagnostics list.

- Exactly-once distributed processing.
- Production-safe public Admin or Kafka diagnostics pages.

- Pre-commit and CI are optional. They run lint, formatting, type checking, unit tests, integration tests, and the frontend test/build. Version 2 CI additionally runs Kafka outbox, worker, ordering, duplicate-message, and recovery tests.
