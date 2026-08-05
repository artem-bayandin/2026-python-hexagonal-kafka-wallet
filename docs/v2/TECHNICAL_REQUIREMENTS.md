# Clean Architecture Wallet — Version 2 Technical Requirements

## 1. Purpose and authority

This document is the canonical architecture contract for Version 2 of the Clean Architecture Wallet. It defines the target technical design for moving admin deposits, user withdrawals, user exchanges, and user transfers from synchronous HTTP execution to asynchronous Kafka command processing.

[README.md](README.md) is authoritative for agreed Version 2 decisions and scope. [Version 1 technical requirements](../v1/TECHNICAL_REQUIREMENTS.md) and the implemented repository define the unchanged baseline; this document replaces only the parts of that baseline that it explicitly changes.

The Version 2 target is not the current implementation. The repository currently implements Version 1 with synchronous wallet commands, immediate `201 Created` responses, `completed|failed` transaction statuses, a single `amount` per user wallet, PostgreSQL-only Docker Compose infrastructure, and no Kafka producer, command worker, reaper, or SSE stream. Version 2 is complete only when the target behavior and quality gates in this document are implemented and verified.

## 2. Architecture outcomes

Every wallet mutation submission returns `202 Accepted` with a `request_id`. The API validates the request, reserves debit funds when applicable, persists a `submitted` transaction, commits, and then publishes a compact command to Kafka. A command worker loads authoritative state from PostgreSQL and executes the mutation. Users observe status changes through Server-Sent Events (SSE), while administrators observe transactions by long polling PostgreSQL.

PostgreSQL is the source of truth for transaction state, financial terms, balances, and debit reservations. Kafka transports execution commands and preserves required partition ordering; it is not the authoritative transaction store. SSE is a notification channel, not a second source of truth.

Delivery and processing are at least once. The design does not claim exactly-once delivery or exactly-once end-to-end processing because Kafka producer guarantees do not make PostgreSQL writes atomic with Kafka publication or offset commits. Duplicate safety comes from a unique `request_id`, guarded transaction states, row locking, and atomic PostgreSQL balance transitions.

Version 2 deliberately has no transactional outbox, no inbox or processed-message table, no persisted database attempts counter, and no Kafka diagnostics API or diagnostics UI. A future outbox may replace only the submit-side publication mechanism without changing the worker command contract, topic layout, user SSE contract, or admin polling contract.

## 3. Technology and dependency policy

The existing stack remains the baseline: Python 3.14 or later as declared by `backend/pyproject.toml`, FastAPI, Pydantic and `pydantic-settings`, async SQLAlchemy 2 with `asyncpg`, PostgreSQL, Alembic, PyJWT, `uv`, Ruff, strict mypy, React, TypeScript, Vite, native `fetch`, plain CSS, ESLint, and Yarn with the `node-modules` linker. Test frameworks (pytest, HTTPX, Vitest, React Testing Library) are deliberately excluded from the current delivery scope; see §15.

The current Compose baseline is PostgreSQL 18.4. Existing direct dependency ranges are declared in `backend/pyproject.toml` and `frontend/package.json`; `backend/uv.lock` and `frontend/yarn.lock` define reproducible resolved builds. This contract does not replace those manifests with copied version lists.

Version 2 adds an Apache Kafka broker, an async Python Kafka client, a command-worker process, and a periodic reaper process or task. The exact broker image and client version are not decided by the authoritative Version 2 decisions and must be selected during implementation from mutually compatible, maintained releases, declared in the appropriate manifest, resolved in the lockfile, and pinned for deployment by an exact image tag or immutable digest. Unsupported Kafka or client versions from superseded drafts are not requirements.

Direct dependencies must use bounded compatible ranges where practical and lockfiles must be committed. Dependency changes require compatibility review, vulnerability review, updated locks, and a successful smoke verification (§15). Major upgrades require explicit migration notes and a manual integration check; Kafka upgrades additionally require a reviewed note on protocol, broker/client compatibility, partitioning, and producer guarantees.

Local infrastructure extends Docker Compose with Kafka and the independently runnable worker and reaper components. Kafka should remain on the internal Compose network unless a local debugging need explicitly requires host exposure. Environment-specific connection values and secrets come from settings and environment files, never source literals.

## 4. Hexagonal architecture and CQRS

The Version 1 Hexagonal Architecture and logical CQRS split remain mandatory. Domain use cases and models are framework-independent; incoming HTTP and Kafka adapters translate transport messages into commands or queries; outgoing ports describe persistence, clock, authentication, publication, and status-notification needs; FastAPI, SQLAlchemy, PyJWT, PostgreSQL, and Kafka remain outer adapters.

`domain/` must not import FastAPI, Pydantic, SQLAlchemy, PyJWT, Kafka-client packages, or adapter DTOs. Domain ports use `typing.Protocol`, commands mutate state and return `Result[T]`, queries return dedicated frozen read models without mutation, and commands and queries share PostgreSQL without event sourcing, separate CQRS databases, a mediator, or a dependency-injection container.

```text
HTTP API ───────────────┐
                       ├──> domain commands and queries <── domain ports
Kafka command worker ──┘                                  ▲
                                                          │
PostgreSQL / auth / Kafka producer / notifier adapters ───┘
```

HTTP authentication state is request-scoped. Submission handlers may use `CurrentUserProvider`, but workers, reapers, and notifier tasks must receive explicit identifiers and must never depend on copied `ContextVar` request state.

Submission and execution are separate use cases. Submission validates immutable financial terms, resolves all required identities and wallets, reserves debit funds, and creates the transaction. Worker execution re-loads that transaction, validates its current guarded state, and applies the already-recorded terms; Kafka payload data must not override PostgreSQL state.

Unexpected infrastructure and programming exceptions escape domain handlers so the active database transaction rolls back. Expected validation and business outcomes use stable `Result.failure` codes. Transport adapters map those outcomes to safe HTTP responses or terminal transaction errors without leaking exception details.

## 5. Target components and folder responsibilities

The existing repository layout remains the base, with responsibilities extended as follows:

```text
backend/app/
├── domain/
│   ├── read_models/          # framework-free transaction, balance, and query projections
│   ├── ports/                # command/query repositories plus publisher, clock, and notifier boundaries
│   └── use_cases/            # submit, execute, status-transition, and existing auth/query handlers
├── api/
│   ├── routers/              # HTTP submission, query, SSE, health, and admin-polling adapters
│   ├── schemas/              # HTTP and SSE transport DTOs
│   └── executors/            # request-scoped transaction and dependency orchestration
├── db/
│   ├── models/               # SQLAlchemy models and database constraints
│   ├── mappers/              # ORM/domain conversion
│   └── repositories/         # command/query adapters and guarded updates
├── kafka/                    # Kafka-facing transport adapters and broker-driven processes
│   ├── messaging/            # Kafka envelope, producer adapter, topic configuration, serialization
│   ├── worker/               # consumer lifecycle, type dispatcher, retry loop, DLQ publication
│   └── reaper/               # stale-submitted scan and safe republication
├── status_notifications/     # swappable notifier adapter used by the SSE boundary
├── auth/                     # unchanged authentication adapters
├── config.py                 # validated API, Kafka, worker, reaper, polling, and timeout settings
├── dependencies.py           # framework-free composition root
└── main.py                   # API lifecycle and router registration
```

Folder names may be refined during implementation, but ownership and dependency direction may not change. The `kafka/` grouping is an internal adapter container: the domain layer never imports from it, and the swappable notifier stays outside it because notifications are not Kafka-coupled. Kafka consumer code must not live in the domain layer, HTTP routers must not perform financial mutations directly, repositories must not own transport policy, and the notifier must not become the authoritative status store.

The command worker is an independent process that reuses domain execution handlers and PostgreSQL repositories. The reaper is independently runnable or scheduled and shares the producer adapter and transaction query/transition ports. The API process owns the SSE endpoint, but the mechanism that detects status changes remains behind the notifier boundary.

No `kafka_api` package, `/kafka/*` route, Kafka message browser, diagnostics database records, or diagnostics frontend view belongs to the Version 2 product surface; the internal `app/kafka/` adapter folder is transport plumbing, not an HTTP or diagnostics surface. Broker state is an operational concern exposed through logs, metrics, health checks, and Kafka administration tooling.

## 6. PostgreSQL migration and persistence contract

All schema changes use reviewed Alembic migrations. Migrations must be applied and exercised from the current Version 1 head, preserve existing transaction history, support a safe deployment sequence, and include reviewed constraints, indexes, lock impact, and downgrade or forward-fix behavior.

The `transactions` table must:

- retain its UUID primary key and immutable type, wallet endpoint, amount, and creation fields;
- add `request_id UUID NOT NULL` with a unique constraint;
- replace the Version 1 status constraint with exactly `submitted|pending|in_progress|succeeded|failed`;
- migrate legacy `completed` rows to `succeeded` and retain legacy `failed` rows as `failed`;
- add nullable `error TEXT`, containing only a safe persisted failure description or code;
- add `updated_at TIMESTAMPTZ NOT NULL`, backfilled from `created_at` for legacy rows and changed on every status transition;
- add indexes that support stale-status scans and the admin `(updated_at, id)` cursor;
- not add `attempts`, outbox, inbox, processed-message, or Kafka-diagnostics columns or tables.

The migration must generate a unique `request_id` for every existing row before enforcing `NOT NULL` and uniqueness. Runtime submission generates the request ID once and uses it consistently in the HTTP response, Kafka envelope, logs, metrics, reaper, worker, DLQ record, and SSE event.

The `user_wallets` table must add `locked_amount` using the same fixed-precision numeric semantics as `amount`, with `NOT NULL DEFAULT 0`, `locked_amount >= 0`, and `amount - locked_amount >= 0` constraints. The existing non-negative `amount` constraint and one-wallet-per-user-and-currency uniqueness remain.

Amounts remain fixed-precision PostgreSQL `NUMERIC`, never floating point. Command amounts must be positive, wallet amounts and locked amounts must remain non-negative, per-currency precision must be enforced without silent rounding, and all financial terms recorded on a transaction are immutable after submission.

## 7. Transaction lifecycle and guarded transitions

The only Version 2 statuses are:

- `submitted`: the API committed the transaction and any debit reservation, but Kafka acknowledgement has not yet been reflected in PostgreSQL;
- `pending`: Kafka acknowledged the command and the worker has not started execution;
- `in_progress`: the worker claimed the command and is executing or retrying it;
- `succeeded`: execution finished and all balance and lock changes committed;
- `failed`: publication or execution ended terminally, the safe error was stored, and any debit reservation was released.

Allowed forward transitions are `submitted → pending`, `submitted → failed`, `pending → in_progress`, and `in_progress → succeeded|failed`. Terminal states never transition. Every transition is a conditional update or an equivalent row-locked check that verifies the expected current state; `updated_at` changes in the same transaction.

The API and reaper set `pending` only after Kafka acknowledges publication. The API may set `failed` from `submitted` after its bounded producer retries are definitively exhausted, releasing any debit reservation in the same PostgreSQL transaction.

A worker receiving a terminal transaction acknowledges and skips it without applying balances. A worker receiving `submitted` must not misclassify it as a duplicate and acknowledge it permanently because Kafka consumption can race the API's post-publish `pending` update; it must defer or retry safely until the transaction becomes `pending`, or until a terminal state is visible. A redelivery of `in_progress` after worker failure is a recovery case and may resume execution under row locks; it is not permission to apply a previously committed mutation again.

The transaction row and wallet rows are the idempotency boundary. The worker must lock or conditionally claim the transaction before mutation, lock all affected wallet rows in deterministic order, inspect current state after locking, and commit financial changes with the terminal status in one PostgreSQL transaction. A duplicate or stale delivery that cannot acquire a valid non-terminal execution state performs no financial mutation.

Clients must tolerate skipped observed states because execution may advance faster than polling or SSE delivery. The canonical lifecycle still applies even when a UI observes `submitted` followed directly by `succeeded`.

## 8. Direct publication and reaper

Submission uses direct publish after commit:

1. Validate the request and resolve immutable transaction terms.
2. In one PostgreSQL transaction, reserve debit funds when required and insert the transaction as `submitted`.
3. Commit the PostgreSQL transaction.
4. Publish the command to Kafka with bounded producer retries.
5. After broker acknowledgement, guard `submitted → pending` in a new PostgreSQL transaction.
6. Return `202 Accepted` with `request_id`.

PostgreSQL commit and Kafka publication are intentionally not one atomic transaction. A process crash between steps 3 and 5 can leave a valid `submitted` row with no message or with an already-accepted message. The reaper closes this ambiguity by scanning only `submitted` rows older than a configured threshold and republishing the same envelope and key; duplicate publication is expected and safe.

After a known publish failure exhausts retries, the API guards `submitted → failed`, stores a safe error, and releases any lock in one transaction. If the process dies before recording that outcome, the row remains `submitted` and the reaper retries it. A reaper publication failure leaves the row `submitted` for a later bounded attempt and emits an operational alert.

After a reaper publish is acknowledged, it guards `submitted → pending`. If another actor already advanced or terminally completed the row, the guarded update is a no-op. The reaper never republishes `pending` or `in_progress` transactions: stale `pending` indicates consumer outage or lag, and stale `in_progress` indicates worker failure requiring alerting and operational recovery.

Reaper scans must be bounded, indexed, safe under concurrent reaper instances, and use row claiming or guarded updates so instances do not create an avoidable publish storm. Reaper age, batch size, schedule, producer timeout, and retry limits are configuration, not domain constants.

## 9. Kafka contract and producer guarantees

The command topic is `wallet`. User withdrawals, exchanges, and transfers use the submitting user's UUID string as the Kafka record key, ensuring that all commands submitted by that user map to one concrete partition and retain Kafka order within that partition. Admin deposits use the fixed literal key `"admin"`, ensuring all deposits map to one admin partition.

The key is part of the producer contract and must never be omitted or randomly generated. Partition counts may vary by environment without changing key semantics. Per-user ordering applies to the submitting user's command stream; correctness for recipient or shared wallet updates still relies on PostgreSQL row locks and deterministic lock ordering.

The command value is the transport-neutral envelope:

```json
{
  "request_id": "uuid",
  "type": "deposit|withdrawal|exchange|transfer",
  "submitted_at": "RFC 3339 timestamp"
}
```

The worker dispatches by `type` and loads all authoritative terms from the `transactions` row identified by `request_id`. Additional financial payload is unnecessary and, if later introduced for diagnostics or compatibility, must never override PostgreSQL. The envelope contains no ORM objects, Pydantic request objects, JWTs, admin keys, OTPs, emails, connection strings, or other secrets.

The consumer group is `wallet-worker`. All command-worker instances join this group so each partition has at most one active group consumer at a time while allowing horizontal scaling up to the partition count.

The producer must request acknowledgement from all in-sync replicas (`acks=all`), enable Kafka producer idempotence, and use bounded retries and timeouts. Producer idempotence reduces duplicate records caused by producer retries within Kafka's supported session semantics; it does not deduplicate reaper publication, make PostgreSQL atomic with Kafka, or justify an exactly-once claim.

The DLQ topic is `wallet.dlq`. DLQ records retain the original key and envelope and add safe failure context sufficient for operations and controlled replay. DLQ consumers must treat `request_id` as the deduplication identity because duplicate DLQ records are possible.

Topic creation, partition count, replication, retention, and development bootstrap must be explicit deployment configuration. Production changes to partitioning require review because increasing partitions changes future key-to-partition mapping and therefore the continuity of per-key ordering across the change.

## 10. Worker dispatch, retries, offsets, and DLQ

The worker validates the envelope, resolves the transaction by `request_id`, verifies that the stored type matches the envelope, and dispatches to one of four execution handlers: deposit, withdrawal, exchange, or transfer. Unknown types, malformed envelopes, missing transactions after a bounded visibility delay, and irreconcilable type mismatches are poison-message failures and must not mutate balances.

One Kafka delivery receives at most three in-process execution attempts. Retryable infrastructure failures use bounded backoff while the transaction remains `in_progress`; deterministic invalid messages and invariant violations do not need repeated attempts. Retry classification must be explicit, reviewable, and must not convert infrastructure faults into invented business outcomes.

There is no database attempts counter. A worker crash or rebalance may cause Kafka redelivery and therefore a new local retry loop. Cross-delivery retry budgets, if ever required, are a future schema and operational design change rather than an implicit Version 2 feature.

On success, the worker commits all wallet mutations, lock settlement, and `in_progress → succeeded` in one PostgreSQL transaction, then commits or acknowledges the Kafka offset. If it crashes before offset acknowledgement, redelivery sees the terminal transaction and skips financial mutation.

After final failure, the worker first publishes the original key and envelope plus safe failure context to the DLQ and waits for broker acknowledgement. It then commits the safe error, debit-lock release, and `in_progress → failed` in one PostgreSQL transaction, and only then acknowledges the original record. This order is mandatory because Version 2 has no persisted `dlq_published` marker: committing `failed` before DLQ acknowledgement would let a crash leave a terminal row whose redelivery is skipped without ever reaching the DLQ.

If the worker crashes after DLQ acknowledgement but before the terminal database commit, redelivery may publish a duplicate DLQ record before completing `failed`; duplicate DLQ publication is acceptable and consumers deduplicate by `request_id`. If the terminal database commit succeeds but source acknowledgement fails, redelivery sees `failed` and safely acknowledges without another financial mutation because DLQ durability was already established.

Malformed messages that cannot identify a transaction cannot update PostgreSQL but must still be sent to the DLQ before the original record is acknowledged. A DLQ publication outage must leave the original record unacknowledged and surface an alert rather than silently dropping it.

The worker must not hold a PostgreSQL transaction open during retry backoff or Kafka network waits. Database transactions must cover only claim, state inspection, and one atomic mutation attempt. Consumer polling and heartbeat configuration must remain compatible with the maximum processing and backoff time so retries do not trigger avoidable rebalances.

## 11. Debit reservation, settlement, and release

Withdrawals, exchanges, and transfers reserve the source amount during submission. Deposits are credit-only and never reserve funds.

The reservation and `submitted` transaction insert occur in the same PostgreSQL transaction. Under a source-wallet row lock or equivalent guarded update, submission increments `locked_amount` only when `amount - locked_amount >= debit_amount`; zero affected rows returns `409 INSUFFICIENT_FUNDS`, creates no transaction, and publishes no Kafka record.

For transfer submission, the recipient is resolved and recorded before commit and revalidated by the worker without changing the recorded financial terms. Exchange records both source and destination amounts and currencies before commit. Withdrawal records the source and admin destination semantics before commit.

Successful execution locks the transaction and all affected wallets in deterministic order. In one PostgreSQL transaction it verifies the reserved amount, decrements source `amount` and `locked_amount` by the debit, credits the destination required by the operation, updates wallet timestamps, and marks the transaction `succeeded`.

Terminal publication or execution failure releases the reservation by decrementing `locked_amount` without decrementing `amount`, and marks the transaction `failed` with a safe error in the same PostgreSQL transaction. Release must be guarded by transaction state so duplicate failure handling cannot unlock twice.

Deposit success credits the destination user wallet without debiting an admin wallet, preserving the Version 1 mock-deposit rule. Withdrawal, exchange, and transfer retain the Version 1 financial rules; Version 2 changes execution timing and adds reservation, not the underlying asset accounting.

`GET /me/balances` exposes total `amount` and `locked` per currency. Spendable balance is `amount - locked`; it may be computed by the API or UI but must use those canonical values and must never be represented by an independently mutable database bucket.

## 12. HTTP, SSE, and admin polling boundaries

The four mutation routes keep their Version 1 request validation and authorization but return `202 Accepted` with `{request_id}`:

- `POST /admin/deposits`;
- `POST /me/withdrawals`;
- `POST /me/exchanges`;
- `POST /me/transfers`.

`GET /me/transactions` includes `request_id`, lifecycle `status`, and safe `error`; `GET /me/balances` includes total `amount` and `locked`. Route DTOs and exact safe error mappings remain owned by the HTTP API contract, but they must preserve the architecture semantics defined here.

`GET /me/stream` is an authenticated SSE endpoint that emits status notifications shaped as `{request_id, status, error?}` only for transactions visible to the current user, including incoming transfers. Because the existing browser authentication contract uses a Bearer header, the frontend must use an authenticated streaming request capable of attaching that header and must never place the JWT in the stream URL. On `succeeded`, the UI refetches balances; on `failed`, it displays the safe error. The UI status component must tolerate reconnects, duplicate events, and skipped observed states.

The notifier is a boundary, not a fixed infrastructure choice. Its implementation mechanism remains swappable and is selected during implementation; acceptable candidates include an in-process event bus, bounded PostgreSQL polling, or PostgreSQL `LISTEN/NOTIFY`. Regardless of mechanism, PostgreSQL remains authoritative, reconnect and missed-event recovery must reconcile from database-backed queries, and horizontal API scaling must not silently lose correctness.

The notifier must not require a Kafka status topic in Version 2. Adding such a topic later is an adapter change if the SSE contract and PostgreSQL source-of-truth rule remain unchanged.

Administrators use long polling on `GET /admin/transactions`, backed only by PostgreSQL and never by Kafka reads. The cursor is the ordered pair `(updated_at, id)`, represented directly or as an opaque encoding; a UUID `id` alone is not monotonic and is not a valid incremental cursor.

The admin query uses the semantic shape `WHERE (updated_at, id) > (:updated_at, :id) ORDER BY updated_at ASC, id ASC`, waits up to a configured bound when no rows are available, and returns the next cursor. Inserts and every status change update `updated_at`, so the same transaction may appear more than once; the admin UI upserts by transaction ID or `request_id`.

## 13. Security

Version 1 OTP, JWT, current-user, and development admin-key rules remain in force. User submission, transaction queries, balances, and SSE require the authenticated user pipeline; admin deposit and polling require the authorized admin boundary. Static admin-key access and demo OTP output remain development-only and must be disabled in production.

SSE authorization must be enforced before streaming and on every database selection used by the stream; a client must never receive another user's transaction status. Disconnect handling must release resources promptly, and reconnect parameters must be validated and bounded.

Kafka commands contain only minimum identifiers and no credentials or personal data. Logs, metrics, traces, DLQ context, and error responses must redact OTPs, JWTs, admin keys, database credentials, Kafka credentials, connection strings, and raw unexpected exceptions.

Kafka must not be publicly exposed by default. Production transport encryption, broker authentication, and topic ACL mechanisms are deployment decisions to be selected before production use; whatever mechanism is chosen must give the API producer write access to `wallet`, the worker read access to `wallet` and write access to `wallet.dlq`, and operations only the minimum required administrative access.

Configuration must fail safely when required secrets or broker settings are absent. Development shortcuts may not be enabled in production. Dependency and container images must be scanned, and security fixes follow an expedited update path.

There is no public or development-only Kafka diagnostics product surface. Operational access to message metadata must use restricted infrastructure tooling and telemetry, not unauthenticated application routes or a browser UI.

## 14. Observability and operations

Structured logs must correlate HTTP submission, PostgreSQL transaction state, producer publication, reaper republication, worker handling, retries, DLQ publication, SSE notification, and admin polling by `request_id`. Relevant records also include operation type, status, Kafka topic, partition, offset, consumer group, retry number within the current delivery, duration, and safe error classification.

Metrics must cover HTTP latency and errors, submission outcomes, publish latency and failures, reaper scan age and republish counts, counts and age by transaction status, Kafka consumer lag, worker throughput and failures by type, local retries, rebalances, DLQ publication, SSE connections and disconnects, admin long-poll duration, and database connectivity and transaction failures.

Alerts must cover aged `submitted` rows, stale `pending` rows with consumer lag or outage, stale `in_progress` rows, repeated reaper failures, DLQ growth, DLQ publication failure, invariant or constraint violations, negative-balance attempts, readiness failure, and sustained worker or producer errors. The reaper does not repair stale `pending` or `in_progress`; those states require operational investigation.

API liveness proves the process is running. API readiness reflects PostgreSQL and the dependencies required to accept wallet submissions. Worker readiness requires PostgreSQL and Kafka connectivity plus valid topic/group configuration. Reaper readiness requires PostgreSQL, Kafka, and its scheduling/leadership mechanism. Shutdown must stop new intake or polling, finish or roll back active database transactions, preserve unacknowledged Kafka work for redelivery, and close SSE connections cleanly.

Operational runbooks must cover broker outage at submission, consumer lag, poison messages, controlled DLQ replay, stuck statuses, worker crash during settlement, reaper duplication, migration failure, and PostgreSQL backup/restore. DLQ replay must reuse the original key and request ID and rely on the same guarded idempotency rules.

## 15. Verification and deferred testing

Automated tests are out of scope for the current Version 2 delivery. Verification is performed as one-time, manually run smoke checks — typically executed by the AI assistant implementing the change — that prove only that the application builds, starts, and returns data that appears valid. A smoke check covers, at minimum:

- backend Ruff lint/format and strict mypy pass;
- frontend ESLint, TypeScript typecheck, and production build pass;
- PostgreSQL and Kafka start from Docker Compose and every process (API, worker, reaper, frontend) reaches readiness;
- authentication succeeds and each enabled wallet route returns a plausible response (`202` with a `request_id` for submissions; well-formed JSON for queries);
- observed database state is consistent with the action taken (transaction row, status, balances, and locks look correct on inspection).

A smoke check is not proof of correctness, idempotency, or recovery behavior; it only establishes that the system is runnable and superficially coherent. Design rules in this document (guarded transitions, duplicate safety, bounded retries, DLQ ordering, redaction) remain mandatory in code even though they are not exercised by an automated suite.

The following suites are deferred to possible future steps and are explicitly not required now:

- unit tests for status-transition guards, duplicate and stale delivery decisions, retry classification, dispatcher selection, envelope validation, reservation rules, settle/release invariants, reaper candidate selection, SSE event mapping, and cursor behavior;
- PostgreSQL integration tests over real Alembic migrations from the Version 1 baseline, including legacy status migration, request-ID backfill, lock constraints, guarded updates, deterministic row locking, and concurrent reservation/settlement behavior;
- Kafka integration tests over a real broker covering topic bootstrap, partitioning, ordering, producer guarantees, offset behavior, duplicate delivery, crash points, retries, malformed messages, DLQ publication, and replay;
- end-to-end tests across all four routes, the full lifecycle, SSE delivery and reconnect, balance refresh, and admin long polling;
- recovery tests that kill or interrupt processes between database, Kafka, and offset boundaries and force producer, consumer, DLQ, and database outages;
- frontend tests for typed API behavior, status rendering, SSE edge cases, and admin cursor upserts;
- CI pipelines enforcing any of the above.

When automated testing is adopted later, it should be reintroduced in the order above, and this section's "not required" status must be revised in the same change.

## 16. Quality and release gates

Every Version 2 change must pass:

- backend Ruff format check and lint;
- backend strict mypy;
- frontend ESLint, TypeScript typecheck, and production build;
- dependency vulnerability review and lockfile consistency;
- the §15 smoke verification covering authentication, one debit command, one deposit, SSE status, admin polling, and worker/DLQ health, performed manually or by the implementing assistant.

Automated tests and CI are deferred per §15. A release is not complete while dependencies or container images float to unpinned versions.

Migrations must be applied before code that depends on the new schema. Rollback is allowed only while schema and written data remain compatible; otherwise use a forward fix or restore. PostgreSQL backup and restore procedures must be exercised before production migration.

## 17. Explicit non-goals

- Transactional outbox, Debezium CDC, inbox, or processed-message tables.
- A persisted worker `attempts` counter or cross-redelivery retry budget.
- Exactly-once delivery or exactly-once end-to-end processing claims.
- Kafka diagnostics HTTP endpoints, Kafka diagnostics database projections, or a Kafka diagnostics frontend.
- Event sourcing, separate CQRS databases, or a Kafka-backed source of truth for balances and transaction status.
- A user WebSocket channel, an admin SSE channel, or admin reads directly from Kafka.
- A mandatory status-event Kafka topic or a fixed SSE notifier implementation before implementation evaluation.
- Production OTP delivery, production static admin authentication, real payment rails, real custody, or AML services beyond the Version 1 sample scope.

## 18. Definition of done

Version 2 is done when all four wallet mutations submit asynchronously with `202` and `request_id`; debit funds are reserved at submission and settle or release atomically; direct post-commit publication and the stale-`submitted` reaper recover the database/Kafka gap; `wallet` commands satisfy key, envelope, ordering, and producer guarantees; the `wallet-worker` group processes every type at least once without double-applying assets; exhausted failures reach `wallet.dlq`; users observe safe status changes over the swappable SSE notifier boundary; administrators observe all inserts and transitions through PostgreSQL long polling on `(updated_at, id)`; security and operational controls are present; and every quality gate passes.
