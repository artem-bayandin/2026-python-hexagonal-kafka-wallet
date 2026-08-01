Build a small custodial-wallet web application in two versions. It uses a React UI and a Python API to demonstrate OTP authentication, USDT/USD balances, mocked deposits, 1:1 exchange, withdrawals, user-to-user transfers, transaction history, Clean/Hexagonal Architecture, CQRS, and asynchronous Kafka processing.

The application is a learning sample. It does not move real money, send real email, perform real AML checks, or provide production-grade administration. [README.md](README.md) defines this document's authority and the version-specific reading order.

## 6. Version 2 — Kafka-executed wallet commands

### 6.1 General command lifecycle

Deposit, exchange, and withdrawal become asynchronous commands:

1. The HTTP endpoint creates a `PENDING` business transaction and an outbox message in one database transaction.
2. The endpoint returns `202 Accepted` with an operation ID.
3. An outbox relay publishes the command to Kafka.
4. Commands use the target user ID as the Kafka partition key so commands for one user retain order.
5. A single worker process consumes commands and dispatches them to deposit, exchange, or withdrawal handlers, with separate USDT/USD handling where required.
6. The worker performs current-state validation and marks the operation `COMPLETED` or `REJECTED`.

Exchange and withdrawal funds are not reserved by the HTTP API. Therefore an accepted command can later be rejected by the worker, for example because a previous queued command spent the available balance.

Message delivery is at least once. Event IDs, operation IDs, inbox/outbox uniqueness, and guarded state transitions make retries idempotent.

### 6.2 Balance buckets

Each user balance exposes:

- `available`: can be exchanged or withdrawn;
- `pending`: cannot be exchanged or withdrawn;
- `rejected`: cannot be exchanged, but can be withdrawn.

### 6.3 Deposit command

The Admin form includes an approval checkbox:

- checked means the mocked AML decision is approval;
- unchecked means the mocked AML decision is rejection.

When the API accepts the deposit, it immediately increments the user's pending bucket and writes the command to the outbox. The selected mock decision travels in the command but is not applied by the API.

The worker moves the amount:

- from `pending` to `available` when approved;
- from `pending` to `rejected` when rejected.

An unexpected infrastructure failure is recorded as `FAILED` and remains retryable; it is not treated as an AML rejection.

### 6.4 Exchange command

The worker validates the assets, precision, and current available source balance. On success it atomically debits the available source balance and credits the available destination balance. On business failure it changes no balance and marks the operation `REJECTED` with a safe reason.

### 6.5 Withdrawal command

The command identifies the asset, amount, and source bucket (`available` or `rejected`). The worker validates and debits that bucket, then credits the matching admin balance. Pending funds cannot be withdrawn.

## 7. Kafka diagnostics

Version 2 provides, only when the explicit development diagnostics flag is enabled:

- a public React route at `/kafka/`;
- unauthenticated, read-only Kafka diagnostics API endpoints;
- pagination and filtering for message records;
- message/command type, operation and correlation IDs;
- state such as `PENDING`, `PUBLISHED`, `PROCESSING`, `COMPLETED`, `REJECTED`, or `FAILED`;
- created, published, processing, and completion timestamps;
- sanitized input data and result/error data.

Kafka is not used as a queryable historical database. Producers and consumers maintain a PostgreSQL message log that powers this page.

All diagnostics HTTP code lives in a self-contained `app/kafka_api/` package with its own router, schemas/DTOs, query service, and read repository. Wallet domain handlers do not import it. It is registered once in application composition so it can later be removed without changing wallet behavior.

JWTs, OTPs, admin keys, and secrets must never be written to the diagnostics payload. This unauthenticated page is a development-only teaching tool, returns `404` when disabled, and must not be enabled unchanged in a real application.

The Vite/React/TypeScript application uses plain CSS and native `fetch`. Version 1 switches views with React state in `App.tsx` (no URL router wired yet); `react-router-dom` is installed as a scaffold dependency for future use.

- **Wallet:** show balances, paginated transaction history, submit exchanges, withdrawals, and transfers, show immediate results in version 1, show pending-operation feedback in version 2, and log out.
- **Admin:** development-only; capture the admin key, create deposits, choose the version-2 mock decision, and show admin balances and all transactions.
- **Kafka:** development-only version-2 message diagnostics without authentication.

- WebSockets; the UI polls operation, balance, and history queries.
- Production exposure of the Admin or Kafka diagnostics pages.
