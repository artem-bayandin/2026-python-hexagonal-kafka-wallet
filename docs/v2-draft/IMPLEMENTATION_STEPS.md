# Implementation Steps

## Version 2 — Kafka-executed commands

## Step 12 — Evolve wallet and operation persistence

- [ ] Add Version 2 pending/rejected balance representation (strategy TBD against `user_wallets` — see [PHASE_6_KAFKA.md](../implementation/PHASE_6_KAFKA.md)).
- [ ] Add transaction statuses `pending`, `rejected`, and additional failure states while retaining `completed`.
- [ ] Add safe failure/result fields and lifecycle timestamps.
- [ ] Add outbox, inbox/processed-message, and Kafka diagnostics message persistence.
- [ ] Add unique message/operation constraints preventing duplicate application.
- [ ] Write and manually review an Alembic migration.
- [ ] Update domain transitions, repositories, read models, and unit tests.

**Done when:** existing version-1 data migrates safely and repository tests cover every new bucket/status transition.

## Step 13 — Define Kafka contracts and infrastructure

- [ ] Define a versioned command envelope with message ID, operation ID, command type, user partition key, correlation/causation IDs, timestamp, and typed payload.
- [ ] Define deposit, exchange, and withdrawal payloads independent of API DTOs and ORM models.
- [ ] Add the pinned Kafka broker and worker services/configuration to Docker Compose.
- [ ] Implement the `aiokafka` producer/consumer adapter behind messaging ports.
- [ ] Implement an outbox relay that safely claims and publishes rows.
- [ ] Record publication attempts, broker metadata, timestamps, and failures.
- [ ] Use target user ID as the message key, `wallet.commands.v1` as the command topic, and `wallet-command-worker-v1` as the consumer group.
- [ ] Document at-least-once delivery explicitly.

**Done when:** a test command can move from PostgreSQL outbox to Kafka and its published state is observable without invoking wallet business behavior.

## Step 14 — Implement asynchronous command submission

- [ ] Replace version-2 deposit, exchange, and withdrawal HTTP behavior with submission handlers that return an operation ID.
- [ ] Persist the pending transaction and outbox command atomically.
- [ ] For deposit only, increment the pending balance in that transaction.
- [ ] Add the Admin approval checkbox value to the deposit command payload.
- [ ] Do not reserve exchange or withdrawal funds at submission.
- [ ] Return `202 Accepted` from all three command endpoints.
- [ ] Add user/admin operation-status queries with ownership/access checks.
- [ ] Test rollback so no pending operation can exist without its outbox row and vice versa.

**Done when:** HTTP submission never directly executes exchange/withdrawal and every accepted operation is discoverable as pending.

## Step 15 — Implement the command worker

- [ ] Create one consumer group and one worker entry point.
- [ ] Add dispatch to deposit, exchange, and withdrawal execution handlers.
- [ ] Record inbox/processing state before execution.
- [ ] Deposit:
      - checked approval moves `pending → available`;
      - unchecked approval moves `pending → rejected`.
- [ ] Exchange:
      - validate current available source funds and precision in the worker;
      - atomically update available source/destination;
      - otherwise reject without balance changes.
- [ ] Withdrawal:
      - validate the requested `available` or `rejected` source bucket;
      - atomically debit user and credit admin;
      - reject pending-bucket requests.
- [ ] Mark business outcomes `COMPLETED` or `REJECTED`.
- [ ] Map expected worker-handler `Result.failure(error_code)` outcomes to `REJECTED` with a safe reason code.
- [ ] Let unexpected exceptions escape the handler, then mark their operations `FAILED` and keep them retryable.
- [ ] Make duplicate delivery return the stored outcome without applying money twice.
- [ ] Preserve per-user command order through Kafka keying and consumer design.

**Done when:** all three commands execute only after Kafka consumption and duplicate messages cannot duplicate any financial effect.

## Step 16 — Build the isolated Kafka diagnostics API

- [ ] Create `app/kafka_api/` with its own router, schemas/DTOs, query service, and read repository.
- [ ] Keep wallet domain and command handlers free of imports from this package.
- [ ] Query PostgreSQL message records rather than attempting to query Kafka history.
- [ ] Add development-profile-only, unauthenticated, read-only endpoints:
      - `GET /kafka/messages`;
      - `GET /kafka/messages/{message_id}`.
- [ ] Support pagination and useful filters such as state, command type, operation ID, and correlation ID.
- [ ] Return input, result/error, broker metadata, and lifecycle timestamps.
- [ ] Sanitize OTPs, JWTs, admin keys, secrets, and connection values before persistence and response.
- [ ] Register this router once in `main.py` so removing registration/package does not change wallet behavior.

**Done when:** the module can be removed from application composition without modifying domain/use-case code and API tests prove that secret fields cannot appear.

## Step 17 — Update the React UI for version 2

- [ ] Update wallet/admin mutations to handle `202 Accepted`.
- [ ] Show pending operation IDs and poll operation status.
- [ ] Display `available`, `pending`, and `rejected` balances per asset.
- [ ] Add Admin's approve/reject checkbox to the deposit form.
- [ ] Let withdrawal select `available` or `rejected`; never offer `pending`.
- [ ] Render completed, rejected, and failed outcomes with safe reasons.
- [ ] Add development-only `/kafka/` route with message list, filters, details, states, timestamps, input, and result/error.
- [ ] Poll diagnostics with the bounded exponential-backoff settings in `CONFIGURATION.md` rather than adding WebSockets.
- [ ] Add focused tests for async status rendering and Kafka diagnostics.

**Done when:** all version-2 states can be demonstrated in the browser, including approved/rejected deposits and worker-rejected exchange/withdrawal.

## Step 18 — Complete version-2 reliability tests

- [ ] Cover outbox retry after broker unavailability.
- [ ] Cover duplicate publication and duplicate consumption.
- [ ] Cover ordered commands for one user.
- [ ] Cover independent processing for different users.
- [ ] Cover an exchange/withdrawal accepted by HTTP but later rejected for insufficient funds.
- [ ] Cover approved and rejected deposits and withdrawals from rejected funds.
- [ ] Cover raised infrastructure exceptions becoming `FAILED` separately from failed `Result` business outcomes becoming `REJECTED`.
- [ ] Cover worker restart and recovery of unfinished messages.
- [ ] Cover Kafka diagnostics filtering, timestamps, payloads, and sanitization.
- [ ] Run all backend/frontend quality checks and verify the startup, demo, release, rollback, backup, and incident procedures in `README.md` and `OPERATIONS.md`.

**Done when:** version 2 demonstrates asynchronous execution, at-least-once delivery, duplicate-message safety, ordering, and observability without claiming production exactly-once guarantees.

## Required completion controls

- [ ] Add CI for backend lint/typecheck/tests, frontend typecheck/tests/build, PostgreSQL integration tests, and version-2 Kafka integration tests.
- [ ] Add architecture decision records for CQRS, generic `Result[T]` plus automatic transaction contexts, PostgreSQL, OTP sessions, outbox/duplicate-message handling, and the removable Kafka diagnostics adapter.
