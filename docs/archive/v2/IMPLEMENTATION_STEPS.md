# Version 2 Implementation Steps

This is the canonical delivery plan for Version 2. Execute it top to bottom, prove every hard stop gate, and do not start a later phase or transaction slice while an earlier gate is red.

All Version 2 work below is target work and remains unchecked until the code exists and a one-time smoke check proves the stated result. Automated test suites and CI are deliberately out of scope for this delivery and are deferred to possible future steps (see [TECHNICAL_REQUIREMENTS.md](TECHNICAL_REQUIREMENTS.md) §15); every "smoke check" below is a manually or AI-run verification that the application builds, starts, and returns data that appears valid.

## Prerequisites and current baseline

Version 1 is the implemented baseline: FastAPI, React, PostgreSQL, Alembic, authentication, synchronous admin deposit and user wallet mutations, transaction history, and the existing Hexagonal Architecture boundaries are present.

Version 2 is not currently implemented: Kafka, the command worker, the reaper, the Version 2 schema, asynchronous submission, SSE, and Version 2 admin long polling are still delivery work. Automated recovery suites and CI are deferred future work, not part of this delivery.

Before Phase 1:

- [x] Reproduce the Version 1 backend and frontend from a clean checkout using committed lockfiles.
- [x] Apply the current Alembic head to a fresh PostgreSQL database and record the revision used as the Version 2 migration baseline.
- [x] Run the existing backend and frontend quality commands and record failures as baseline debt; do not silently attribute pre-existing failures to Version 2.
- [x] Confirm the four Version 1 financial paths and their observable behavior before changing execution timing.
- [x] Confirm local Docker Compose, database credentials, and secret handling are understood.
- [x] Create an implementation branch and a rollback point that preserves the last runnable Version 1 state.

**Prerequisite gate:** do not start Phase 1 until Version 1 can be built, migrated, and exercised well enough to distinguish migration defects from existing defects.

## Non-negotiable delivery rules

- [ ] Follow strict `Domain → DB → API → UI` order inside every slice where those layers apply; a later layer may be designed, but it may not be merged as working behavior before the prior layer passes.
- [ ] Follow strict transaction-slice order: `deposit → withdrawal → exchange → transfer`; no parallel leapfrogging and no starting the next slice with a failing prior-slice gate.
- [ ] Keep PostgreSQL authoritative for transaction state, immutable financial terms, balances, and locks; Kafka transports commands only.
- [ ] Use only `submitted`, `pending`, `in_progress`, `succeeded`, and `failed`; terminal states never transition.
- [ ] Use `request_id` as the stable public and correlation identity across HTTP, PostgreSQL, Kafka, worker, reaper, DLQ, SSE, logs, and admin updates.
- [ ] Generate `request_id` once, enforce uniqueness in PostgreSQL, and never replace it during retry, redelivery, republication, or replay.
- [ ] Publish only the compact envelope `{request_id, type, submitted_at}`; the worker reloads authoritative terms from PostgreSQL and rejects envelope/type disagreement.
- [ ] Key user commands by the submitting user UUID string and deposits by the literal `admin`; no command may be published without a key.
- [ ] Preserve per-key order and review every partition-count change because future key placement can change when partitions increase.
- [ ] Use `acks=all`, Kafka producer idempotence, bounded retries, and bounded delivery timeout for API, reaper, and DLQ publication.
- [ ] Treat processing as at least once; Kafka acknowledgement is never proof that a PostgreSQL financial mutation committed.
- [ ] Make duplicate safety a database property through unique identity, guarded status transitions, row locks, deterministic wallet-lock order, and atomic terminal commits.
- [ ] Reserve debit funds at submission for withdrawal, exchange, and transfer; deposit is credit-only and never reserves funds.
- [ ] Insert `submitted` and reserve the debit in one PostgreSQL transaction, then commit before publishing.
- [ ] Set `pending` only after broker acknowledgement; on definitive bounded publication failure, atomically set `failed`, release any reservation, and store a safe error.
- [ ] Never hold a PostgreSQL transaction open during Kafka I/O, retry backoff, SSE waiting, or admin long-poll waiting.
- [ ] Commit wallet mutation, reservation settlement or release, and terminal status in one PostgreSQL transaction before acknowledging the source record.
- [ ] Never republish stale `pending` or `in_progress`; alert and investigate them.
- [ ] Publish exhausted or poison failures to `wallet_dlq` before acknowledging the original record; duplicate DLQ records are acceptable, silent loss is not.
- [ ] Keep domain code free of FastAPI, Pydantic, SQLAlchemy, Kafka-client, and transport DTO imports.
- [ ] Keep HTTP authentication request-scoped; worker, reaper, and notifier paths receive explicit identifiers and never depend on request context.
- [ ] Expose only safe client errors; redact secrets, credentials, personal data, raw exceptions, and unrestricted payloads from HTTP, SSE, logs, metrics, traces, and DLQ context.
- [ ] Keep the Admin page and static admin key development-only; production stays blocked until approved admin authorization exists.
- [ ] Do not claim a phase complete with floating dependencies or images, undocumented launch commands, or a smoke check that was planned but not actually run.

## Cross-phase proof matrix

The following evidence accumulates throughout the plan and becomes release-blocking at the first phase where the capability exists. In this delivery the evidence comes from code inspection and one-time smoke checks rather than automated suites; full automated proof of each item is deferred (see [TECHNICAL_REQUIREMENTS.md](TECHNICAL_REQUIREMENTS.md) §15).

- [ ] Schema compatibility: upgrade from the Version 1 head, legacy `completed → succeeded`, retained legacy `failed`, unique backfilled `request_id`, backfilled `updated_at`, exact constraints, required indexes, and documented downgrade prohibition or reviewed path.
- [ ] Status guards: every allowed transition succeeds once, stale/illegal transitions affect zero rows, `updated_at` changes atomically, and terminal rows remain terminal.
- [ ] Duplicate safety: duplicate publication, duplicate consumption, redelivery after commit, and controlled replay produce at most one financial effect and at most one reservation release.
- [ ] Partitioning and order: every user command uses the submitting user key, every deposit uses `admin`, equal keys map to one partition, and observed consumption order matches production order for that key.
- [ ] Reserve/settle/release: concurrent submissions cannot overspend; success decrements source `amount` and `locked_amount`; failure decrements only `locked_amount`; all constraints remain valid.
- [ ] Worker crash points: prove behavior before claim, after claim, before financial commit, after terminal commit, before DLQ acknowledgement, and before source-offset acknowledgement.
- [ ] Producer gap: prove crashes after database commit, after broker acknowledgement, and before `pending`; stale `submitted` remains recoverable without double application.
- [ ] Retry and DLQ: exactly three local execution attempts for retryable failures, no unnecessary retries for poison input, bounded backoff, safe terminal failure, acknowledged DLQ publication, and source acknowledgement only afterward.
- [ ] SSE: authenticated isolation, reconnect with `Last-Event-ID`, duplicate delivery, skipped observations, status-regression rejection, snapshot reconciliation, balance refresh on success, safe failure display, and resource cleanup.
- [ ] Admin updates: valid opaque `(updated_at, id)` cursor behavior, repeated row updates, client upsert by identity, cursor advancement only after processing, timeout semantics, malformed-cursor rejection, and transient retry backoff.
- [ ] Operations: readiness, graceful shutdown, structured correlation, bounded-cardinality metrics, alerts, runbooks, backup/restore, migration recovery, release order, and rollback compatibility are documented and exercised.
- [ ] Quality: Ruff lint and format check, strict mypy, frontend lint/typecheck/build, dependency and image review, and the smoke verification all pass.

## Phase 1 — Kafka infrastructure

### Prerequisites

- [ ] The prerequisite gate is green.
- [ ] Broker and Python client choices are mutually compatible, maintained, vulnerability-reviewed, and recorded without weakening the contracts.
- [ ] Local network topology, topic ownership, process ownership, and secret boundaries are agreed.

### Domain

- [ ] Define framework-free publisher and clock ports needed by later submission and recovery use cases.
- [ ] Define the transport-neutral command envelope model with exactly `request_id`, `type`, and `submitted_at`.
- [ ] Define transaction-type validation for `deposit`, `withdrawal`, `exchange`, and `transfer` without importing Kafka types.

### DB

- [ ] Make no Version 2 schema change in this phase.

### API and process infrastructure

- [ ] Add a pinned Kafka broker to Docker Compose with a health check, named storage where required, and no public listener by default.
- [ ] Provision `wallet` and `wallet_dlq` explicitly; use three local `wallet` partitions by default and never rely on broker auto-creation.
- [ ] Add the async Kafka client through the backend package manager, update the lockfile, and review broker/client compatibility.
- [ ] Implement validated settings exactly as specified for broker security, fixed topic names, producer timeouts/retries, worker group, worker liveness, reaper, SSE, and admin polling ownership.
- [ ] Fail startup on invalid profile, missing owned settings, topic mismatch, incompatible timeout relationships, or prohibited production shortcuts.
- [ ] Implement the producer adapter with `acks=all`, producer idempotence, bounded retry/backoff, bounded delivery timeout, explicit key, and safe structured telemetry.
- [ ] Add independently runnable worker and reaper process shells with dependency validation and graceful startup/shutdown, but no wallet execution or republication behavior yet.
- [ ] Extend readiness so each process checks only its owned dependencies, schema expectation, topic metadata, and permissions.
- [ ] Add least-privilege deployment guidance: API and reaper write `wallet`; worker reads `wallet` and writes `wallet_dlq`; applications receive no broad broker-administration rights.

### UI

- [ ] Make no product UI change in this phase.
- [ ] Keep all Kafka connection and credential values out of frontend build variables and assets.

### Smoke check

- [ ] Start the Compose broker and confirm `wallet` and `wallet_dlq` exist with the reviewed partition, retention, and replication settings.
- [ ] Publish a few sample keyed messages and consume them back, confirming identical keys land on one partition and per-key order holds.
- [ ] Confirm an attempted publish without a key is rejected before network I/O.
- [ ] Confirm the worker and reaper shells start, reach readiness, and shut down cleanly.

### Migration and rollback concerns

- [ ] Keep Phase 1 deployable without changing financial behavior or the database schema.
- [ ] Document how to stop the new process shells and remove Kafka from local startup while leaving Version 1 API behavior intact.
- [ ] Pin images and lock dependencies so rollback restores the exact prior dependency graph.
- [ ] Prohibit partition-count changes during rollback or incident response without an ordering-impact review.

### Hard stop gate

- [ ] The one-time broker smoke check shows explicit topic creation, key placement, per-key order, readiness, and a bounded publish failure surfacing as an error.
- [ ] Backend lint, format, strict mypy, dependency review, and lockfile consistency pass.
- [ ] No wallet route publishes and no worker mutates balances yet.

**Done when:** Kafka infrastructure is reproducible, secured by configuration boundaries, observable, independently runnable, and proven without changing Version 1 wallet behavior.

## Phase 2 — Asynchronous schema and state machine

### Prerequisites

- [ ] Phase 1 hard stop gate is green.
- [ ] The exact Version 1 Alembic head and representative legacy data set are available for the upgrade exercise.
- [ ] Lock duration and table size assumptions are measured against production-like data.

### Domain

- [ ] Replace Version 1 transaction status behavior with exactly `submitted`, `pending`, `in_progress`, `succeeded`, and `failed`.
- [ ] Define allowed transitions `submitted → pending`, `submitted → failed`, `pending → in_progress`, and `in_progress → succeeded|failed`.
- [ ] Define terminal-state, duplicate-delivery, stale-delivery, and `submitted`-race decisions explicitly.
- [ ] Extend transaction and balance read models with `request_id`, `status`, safe nullable `error`, `updated_at`, and `locked`.
- [ ] Define reservation, settlement, and release invariants using `Decimal` and existing currency precision.

### DB

- [ ] Add `transactions.request_id UUID`, backfill a unique value for every legacy row, then enforce `NOT NULL` and uniqueness.
- [ ] Replace the status constraint with the exact Version 2 set and migrate legacy `completed` rows to `succeeded` while retaining legacy `failed`.
- [ ] Add nullable `transactions.error` for safe persisted failure information.
- [ ] Add `transactions.updated_at TIMESTAMPTZ NOT NULL`, backfill from `created_at`, and update it on every runtime status transition.
- [ ] Add `user_wallets.locked_amount` with matching numeric semantics, `NOT NULL DEFAULT 0`, `locked_amount >= 0`, and `amount - locked_amount >= 0`.
- [ ] Preserve existing non-negative amount and wallet uniqueness constraints.
- [ ] Add indexes for status/age scans and `(updated_at, id)` cursor reads; verify query plans.
- [ ] Implement repository methods for guarded transitions, row-locked state inspection, conditional reservation, atomic release, and deterministic wallet locking.
- [ ] Ensure financial terms become immutable after submission.
- [ ] Manually review generated DDL, data backfills, constraint ordering, index creation, lock impact, and transaction boundaries.

### API

- [ ] Update internal response mapping and schemas to represent Version 2 fields without switching mutation routes to asynchronous execution yet.
- [ ] Keep externally active Version 1 mutation behavior behind an explicit compatibility boundary until Phase 3 slices replace it.
- [ ] Ensure no mixed deployment writes a status that another live process cannot read.

### UI

- [ ] Update shared TypeScript types for `request_id`, Version 2 statuses, `error`, `updated_at`, and `locked`, but do not expose incomplete target behavior.
- [ ] Add pure status-order and balance-display utilities that tolerate skipped observations and never regress terminal state.

### Smoke check

- [ ] Run the Alembic upgrade once from the exact Version 1 head against representative legacy data.
- [ ] Inspect migrated rows: legacy status conversion, unique request-ID backfill, timestamp backfill, and default zero locks look correct.
- [ ] Spot-check that a guarded transition and a debit reservation through the new repositories return plausible results and respect `0 <= locked_amount <= amount`.
- [ ] Confirm the cursor and stale-scan indexes exist and sample queries use them.

### Migration and rollback concerns

- [ ] Back up PostgreSQL before applying the migration in any persistent environment and verify a recent isolated restore.
- [ ] Define the expand/deploy/contract sequence needed to prevent old code from writing incompatible statuses.
- [ ] State explicitly whether downgrade is safe before Version 2 writes and prohibit schema downgrade after incompatible statuses or locks exist unless a reviewed conversion exists.
- [ ] Prefer a forward fix when Version 2 data cannot be represented by Version 1.
- [ ] Keep API, worker, and reaper code requiring the new schema disabled until the migration revision is verified.

### Schema compatibility hard stop gate

- [ ] Upgrade from Version 1 completes with no lost transaction history, duplicate `request_id`, invalid lock, or unsupported status.
- [ ] The smoke check exercises status guards, reservation constraints, deterministic locks, and cursor reads against a real database without anomalies.
- [ ] Rollback or forward-fix policy is written and approved.
- [ ] Backend lint, format, and strict mypy pass.

**Done when:** the Version 2 schema and state machine are compatible with migrated Version 1 data, enforce invariants in PostgreSQL, and are safe for the first asynchronous slice.

## Phase 3 — Shared submission/worker skeleton and transaction slices

Phase 3 is sequential. Complete the shared skeleton, then deliver exactly one transaction type at a time in the order below. A slice is not complete at `202`; it includes submit, publish, consume, execute, terminal state, duplicate safety, failure handling, and the smallest useful UI adaptation.

Phase 3 and Phase 4 are integration milestones, not production-release points. Until the Phase 5 reaper gate is green, a crash in the database-to-Kafka publication gap can leave `submitted` work requiring explicit operational containment; do not open Version 2 mutation traffic to an environment that depends on unattended recovery.

### Shared skeleton

#### Prerequisites

- [ ] Phase 2 schema compatibility hard stop gate is green.
- [ ] Kafka, PostgreSQL, topics, migration revision, process settings, and permissions pass readiness.
- [ ] Retry classifications and safe error mappings are reviewed before worker behavior is implemented.

#### Domain

- [ ] Separate submission use cases from execution use cases; neither transport adapter owns financial logic.
- [ ] Define submission output as the durable `request_id`.
- [ ] Define execution dispatch by stored transaction type and explicit identifiers, never request-scoped authentication state.
- [ ] Define retryable, deterministic poison, terminal duplicate, `submitted` race, and `in_progress` recovery decisions.
- [ ] Define shared reservation, guarded release, terminal commit, and status-notification ports.

#### DB

- [ ] Implement a submission transaction that records immutable terms, conditionally reserves debit funds when required, and inserts `submitted`.
- [ ] Commit submission before any Kafka call.
- [ ] Implement guarded post-ack `submitted → pending` in a new transaction.
- [ ] Implement guarded publication-failure `submitted → failed` with atomic reservation release and safe error.
- [ ] Implement worker claim and recovery using transaction-row locking or equivalent guarded state inspection.
- [ ] Lock all affected wallet rows in deterministic order and re-check state after locks are acquired.
- [ ] Commit financial mutation, settlement or release, and terminal status atomically.
- [ ] Ensure duplicate terminal handling and duplicate failure handling perform no wallet mutation.

#### API and worker

- [ ] Build the shared submission orchestrator: validate and persist, commit, publish with the required key, guard to `pending` after acknowledgement, or guard to `failed` after definitive bounded failure.
- [ ] Return `202 Accepted` with `{request_id}` for every durable accepted submission, including a submission whose immediate publication path records terminal `failed`.
- [ ] Make the worker defer or safely retry a consumed transaction still in `submitted`; it must not acknowledge it as a duplicate.
- [ ] Validate every envelope, load by `request_id`, compare stored type, and dispatch only after authoritative state checks.
- [ ] Implement exactly three local attempts for retryable execution failures with bounded backoff while status remains `in_progress`.
- [ ] Do not hold a database transaction during backoff or Kafka waits.
- [ ] On success, commit the terminal database transaction before acknowledging the source record.
- [ ] On exhausted or poison failure, publish the original key/envelope plus safe context to `wallet_dlq` and await acknowledgement before atomically persisting safe terminal failure and releasing any reservation; acknowledge the source record only after both are durable.
- [ ] If DLQ publication fails, leave the source record unacknowledged and alert.
- [ ] Do not commit `failed` before DLQ acknowledgement unless a future schema adds a durable DLQ-publication marker; otherwise a crash can leave a terminal row whose redelivery skips a missing DLQ record.
- [ ] Emit structured correlation for publish attempt/ack, guard outcome, delivery, claim, retry, terminal commit, DLQ ack, and source ack without implying cross-system atomicity.

#### UI

- [ ] Add a shared typed `202` response path and reconcile submissions by `request_id`.
- [ ] Prevent forms from presenting `202` as financial success.
- [ ] Display total, locked, and derived spendable values where debit slices use reservations.
- [ ] Defer live transport behavior to Phase 4; use authoritative transaction refresh after submission during Phase 3.

#### Smoke check

- [ ] Carry one no-op command through submit, publish, guarded claim, terminal handling, redelivery, and DLQ paths while watching PostgreSQL rows and logs.
- [ ] Restart the worker once mid-processing and confirm redelivery does not produce a second mutation.
- [ ] Send one malformed envelope and one unknown type and confirm nothing mutates and the DLQ path is taken.

#### Migration and rollback concerns

- [ ] Keep each converted route behind an explicit deployment boundary so old synchronous and new asynchronous execution cannot both apply the same submission.
- [ ] Deploy migrated schema and verified topics before enabling producers or workers.
- [ ] Stop new mutation intake before rolling back a converted route; decide whether compatible workers drain or stop.
- [ ] Forbid deployment of Version 1 synchronous mutation code over live Version 2 transactions unless schema, statuses, locks, and accepted work are demonstrably compatible.

#### Shared skeleton hard stop gate

- [ ] The skeleton smoke check exercises status guards, source-offset ordering, bounded retries, DLQ publication, crash recovery decisions, and duplicate no-op behavior with a real broker and PostgreSQL without anomalies.
- [ ] No transaction type is enabled until the common failure paths are exercised.

**Done when:** the shared machinery can safely carry a no-op smoke command through submit, publish, guarded claim, terminal handling, redelivery, and DLQ paths without implementing wallet-specific effects.

### Slice 1 — Admin deposit

#### Prerequisites

- [ ] The shared skeleton hard stop gate is green.
- [ ] Deposit Version 1 financial semantics and target-recipient rules are confirmed against the running Version 1 baseline.

#### Domain

- [ ] Implement deposit submission validation for normalized recipient email, supported asset, precision, and positive amount.
- [ ] Record the resolved recipient and immutable credit terms at submission.
- [ ] Implement deposit execution as a credit-only command with no reservation.

#### DB

- [ ] Persist one `submitted` deposit with unique `request_id` and resolved destination.
- [ ] Create or lock the destination wallet safely and credit it with `in_progress → succeeded` in one transaction.
- [ ] Use deterministic locks where wallet creation or concurrent deposits can conflict.
- [ ] Persist `failed` safely without changing a wallet when execution cannot complete.

#### API and worker

- [ ] Convert `POST /admin/deposits` to `202 Accepted` with `{request_id}`.
- [ ] Require the development admin boundary and prohibit production exposure.
- [ ] Publish deposits to `wallet` with key `admin`.
- [ ] Dispatch and execute deposit in the worker through the shared retry, DLQ, and acknowledgement path.
- [ ] Include deposit lifecycle fields in admin transaction reads.

#### UI

- [ ] Update the development Admin deposit form for `202` and show accepted state by `request_id` without claiming success.
- [ ] Refresh authoritative admin transaction and balance data after terminal observation available in this phase.
- [ ] Keep safe errors separate from internal failure detail.

#### Smoke check

- [ ] Submit a deposit through the admin UI and confirm `202` with a `request_id`, then watch the lifecycle reach a terminal state.
- [ ] Inspect the database: the destination wallet shows exactly one credit and the transaction projection looks correct.
- [ ] Repeat the same submission flow once after a worker restart and confirm no second credit appears.
- [ ] Confirm admin authorization is required and deposits land on the single `admin` partition in order.

#### Migration and rollback concerns

- [ ] Disable the synchronous deposit executor when the asynchronous route is enabled.
- [ ] Preserve accepted deposit work during deployment and rollback; do not reopen intake until compatible workers are available.
- [ ] Confirm rollback cannot run a synchronous deposit against an already accepted Version 2 transaction.

#### Deposit hard stop gate

- [ ] The deposit smoke check passes submission, `admin` key/order, lifecycle to terminal, exactly one credit on inspection, and UI acceptance behavior.
- [ ] All shared and deposit-specific quality checks pass.

**Done when:** admin deposits execute only in the worker, return `202` with `request_id`, preserve admin order, and credit exactly once.

### Slice 2 — User withdrawal

#### Prerequisites

- [ ] The deposit hard stop gate is green.
- [ ] Withdrawal accounting, admin-wallet credit semantics, and lock ordering are explicit and reviewed.

#### Domain

- [ ] Implement withdrawal submission validation and source reservation against spendable `amount - locked_amount`.
- [ ] Implement success settlement by decrementing user `amount` and `locked_amount` and crediting the matching admin wallet.
- [ ] Implement guarded failure release by decrementing only `locked_amount`.

#### DB

- [ ] Reserve and insert `submitted` atomically; zero affected reservation rows return `409 INSUFFICIENT_FUNDS`, create no transaction, and publish nothing.
- [ ] Lock transaction, user wallet, and admin wallet in deterministic order.
- [ ] Commit settlement and `succeeded` atomically.
- [ ] Commit release, safe error, and `failed` atomically for publication or execution failure.
- [ ] Ensure concurrent withdrawals cannot reserve more than spendable funds.

#### API and worker

- [ ] Convert `POST /me/withdrawals` to authenticated `202 Accepted` with `{request_id}`.
- [ ] Publish with the submitting user UUID key.
- [ ] Execute only the immutable stored terms and use the shared retry, DLQ, and acknowledgement path.
- [ ] Return `amount` and `locked` from balance reads and lifecycle fields from user transaction reads.

#### UI

- [ ] Update withdrawal submission for `202` and reconcile by `request_id`.
- [ ] Display total, locked, and derived spendable values distinctly.
- [ ] Refresh authoritative balances and history after terminal observation available in this phase.
- [ ] Show synchronous insufficient-funds errors separately from later terminal failures.

#### Smoke check

- [ ] Submit a withdrawal and confirm `202`, immediate reservation visibility in the balance read, and a terminal settle or release in the database.
- [ ] Submit a withdrawal exceeding spendable funds and confirm `409 INSUFFICIENT_FUNDS`, no transaction row, and nothing published.
- [ ] Repeat a submission after a worker restart and confirm funds are not debited twice.
- [ ] Submit two rapid withdrawals for one user and confirm order is preserved and the result does not overspend.

#### Migration and rollback concerns

- [ ] Disable the synchronous withdrawal executor when the asynchronous route is enabled.
- [ ] Reconcile outstanding locks before rollback and do not run code that ignores `locked_amount`.
- [ ] Stop intake and choose a compatible drain or stop policy for accepted withdrawals.

#### Withdrawal hard stop gate

- [ ] The withdrawal smoke check covers reserve, ordered worker execution, settle/release, restart redelivery without double debit, `202`, balance projection, and UI spendable behavior.
- [ ] Lock reconciliation on inspection reports no mismatch after the smoke scenarios.

**Done when:** withdrawals reserve synchronously, execute asynchronously, settle or release atomically, and cannot double-debit or over-reserve.

### Slice 3 — User exchange

#### Prerequisites

- [ ] The withdrawal hard stop gate is green.
- [ ] Both exchange directions, destination precision, exact 1:1 representability, and deterministic two-wallet locking are explicit and reviewed.

#### Domain

- [ ] Implement exchange submission validation for supported distinct assets, positive amount, source and destination precision, exact representability, and spendable funds.
- [ ] Record immutable source and destination terms before publication.
- [ ] Implement success settlement by decrementing source `amount` and `locked_amount` and crediting destination `amount` at 1:1.
- [ ] Implement guarded source-reservation release on terminal failure.

#### DB

- [ ] Reserve the source and insert `submitted` atomically.
- [ ] Lock source and destination wallets in deterministic identity order, independent of exchange direction.
- [ ] Commit both wallet mutations, settlement, and `succeeded` in one transaction.
- [ ] Commit release and `failed` atomically without changing destination funds.
- [ ] Ensure opposite-direction concurrent exchanges do not deadlock or overspend.

#### API and worker

- [ ] Convert `POST /me/exchanges` to authenticated `202 Accepted` with `{request_id}`.
- [ ] Publish with the submitting user UUID key.
- [ ] Revalidate persisted invariants without replacing immutable terms from the envelope.
- [ ] Use the shared retry, DLQ, source-acknowledgement, and safe-error behavior.

#### UI

- [ ] Update exchange submission for `202` and reconcile by `request_id`.
- [ ] Prevent same-asset submission and display precision errors safely.
- [ ] Show reservation immediately through authoritative balances and refresh both assets after terminal success.

#### Smoke check

- [ ] Run one exchange in each direction and confirm source settle and destination credit look exact, with no rounding.
- [ ] Confirm same-asset submission and insufficient spendable funds are rejected safely.
- [ ] Repeat a submission after a worker restart and confirm the source is not settled twice and the destination is not credited twice.
- [ ] Confirm per-user order holds when an exchange follows a withdrawal for the same user.

#### Migration and rollback concerns

- [ ] Disable the synchronous exchange executor when the asynchronous route is enabled.
- [ ] Reconcile source locks and both asset balances before rollback.
- [ ] Do not deploy code that can reinterpret stored exchange terms or silently round them.

#### Exchange hard stop gate

- [ ] The exchange smoke check covers exact money semantics, deterministic locking, reserve/settle/release, restart redelivery safety, ordered execution, `202`, and UI reconciliation.
- [ ] Withdrawal and deposit smoke behavior remains intact.

**Done when:** both exchange directions execute exactly once from immutable stored terms with no rounding, deadlock, overspend, or leaked reservation.

### Slice 4 — User transfer

#### Prerequisites

- [ ] The exchange hard stop gate is green.
- [ ] Recipient resolution, self-transfer rejection, same-asset semantics, and sender/recipient lock ordering are explicit and reviewed.

#### Domain

- [ ] Implement transfer submission validation for normalized recipient email, existing recipient, non-self target, supported asset, precision, positive amount, and spendable funds.
- [ ] Record the resolved recipient and immutable same-asset terms before publication.
- [ ] Revalidate recipient consistency during execution without changing recorded terms.
- [ ] Implement success settlement from sender reservation to recipient credit and guarded release on terminal failure.

#### DB

- [ ] Resolve and record the recipient, reserve sender funds, and insert `submitted` atomically.
- [ ] Lock sender and recipient wallets in deterministic identity order.
- [ ] Commit sender `amount`/`locked_amount` decrement, recipient credit, and `succeeded` atomically.
- [ ] Commit reservation release and `failed` atomically when execution cannot proceed.
- [ ] Ensure reciprocal concurrent transfers do not deadlock, lose updates, or create funds.

#### API and worker

- [ ] Convert `POST /me/transfers` to authenticated `202 Accepted` with `{request_id}`.
- [ ] Publish with the submitting sender UUID key; recipient identity never replaces the partition key.
- [ ] Execute through the shared retry, DLQ, acknowledgement, safe-error, and redelivery paths.
- [ ] Preserve user-history ownership and transfer `direction` rules for sender and recipient views.

#### UI

- [ ] Update transfer submission for `202` and reconcile by `request_id`.
- [ ] Keep recipient selection email-based, prevent self-transfer, and display safe synchronous and terminal errors.
- [ ] Refresh sender balances and relevant transaction history after terminal success.

#### Smoke check

- [ ] Run one transfer and confirm sender settle, recipient credit, and correct `direction` in both users' histories.
- [ ] Confirm missing recipient, self-transfer, and insufficient spendable funds are rejected safely.
- [ ] Repeat a submission after a worker restart and confirm the sender is not debited twice and the recipient is not credited twice.
- [ ] Confirm one authenticated user cannot read another user's unrelated transactions.

#### Migration and rollback concerns

- [ ] Disable the synchronous transfer executor when the asynchronous route is enabled.
- [ ] Reconcile sender locks and both wallets before rollback.
- [ ] Preserve already resolved recipients and accepted work; never reconstruct identity from a mutable client payload during recovery.

#### Transfer hard stop gate

- [ ] The transfer smoke check covers sender-key order, deterministic cross-user locks, ownership, reserve/settle/release, restart redelivery safety, `202`, and UI reconciliation.
- [ ] All four transaction-slice smoke checks pass together.

**Done when:** all four transaction types use one proven asynchronous path, and transfer completes the sequence without regressing earlier gates.

## Phase 4 — User live status with SSE and Wallet UI

### Prerequisites

- [ ] The transfer hard stop gate is green.
- [ ] `GET /me/transactions` is the authoritative user snapshot and exposes all Version 2 lifecycle fields.
- [ ] The notifier mechanism has been evaluated for correctness under the intended API replica topology.

### Domain

- [ ] Define a status-notification port and framework-free event read model containing `request_id`, `status`, and nullable safe `error`.
- [ ] Define monotonic client reconciliation rules: upsert by identity, compare `updated_at` from snapshots, ignore status regressions, and accept skipped observations.

### DB

- [ ] Implement the database-backed status-change query or notifier adapter needed for resumable events while keeping PostgreSQL authoritative.
- [ ] Use an opaque event ID that can resume after the last fully processed change.
- [ ] Ensure every status transition updates the fields used by resume ordering in the same transaction.
- [ ] Bound queries, use supporting indexes, and release database resources promptly on disconnect.

### API

- [ ] Add authenticated `GET /me/stream` returning `text/event-stream; charset=utf-8`, `Cache-Control: no-cache, no-transform`, and `X-Accel-Buffering: no`.
- [ ] Emit `transaction_status` events with opaque `id` and JSON `data`.
- [ ] Send non-semantic heartbeat comments at the configured interval and optional retry guidance of at least three seconds.
- [ ] Validate authentication before streaming and scope every event query to the authenticated user.
- [ ] Accept standard `Last-Event-ID`; resume at least once when possible and start a fresh live stream without error when the ID is absent, expired, or unrecognized.
- [ ] Close the connection, rather than appending a JSON error envelope, after a streamed response has started and an error occurs.
- [ ] Disable buffering, compression, and caching through application and trusted proxy configuration.
- [ ] Ensure disconnect cancellation releases tasks, database sessions, queues, and subscriptions.

### UI

- [ ] Connect through an authenticated streaming request that attaches the Bearer header, parses SSE framing, and never places the JWT in the URL; native `EventSource` alone is insufficient for this header-based authentication contract.
- [ ] Reconnect with the last fully processed event ID and bounded retry delay.
- [ ] Call `GET /me/transactions` after every initial connection and reconnection.
- [ ] Upsert events by `request_id`, tolerate duplicates and skipped states, and ignore regressions.
- [ ] Render lifecycle status without assuming every intermediate state was observed.
- [ ] On `succeeded`, refetch authoritative balances and relevant history.
- [ ] On `failed`, clear temporary submission state, refetch authoritative history/balances, and display only the safe error.
- [ ] Display a degraded live-update state without treating cached browser state as authoritative.

### Smoke check

- [ ] Connect to `GET /me/stream` with a Bearer token, submit a transaction, and watch `transaction_status` events arrive with plausible payloads.
- [ ] Disconnect and reconnect with `Last-Event-ID` and confirm the stream resumes or restarts cleanly and the UI reconciles to the authoritative snapshot.
- [ ] Confirm a second user's stream does not receive the first user's events, and that missing or invalid authentication is rejected.
- [ ] Confirm balances refresh after a `succeeded` event and no false success appears from `202` or `pending`.

### Migration and rollback concerns

- [ ] Phase 4 requires no new authoritative status store; any notifier-specific schema change must receive its own reviewed migration and rollback analysis.
- [ ] Keep transaction/history HTTP queries usable when SSE is disabled or degraded.
- [ ] If authorization isolation is uncertain, disable SSE immediately without disabling safe authenticated snapshots.
- [ ] Roll back frontend and API SSE changes together when event or resume compatibility changes.

### SSE hard stop gate

- [ ] A forced disconnect and reconnect across rapid status changes reaches the correct PostgreSQL snapshot with no regression or cross-user disclosure.
- [ ] The SSE smoke check covers reconnect, skipped states, duplicates, and cross-user isolation without anomalies.
- [ ] Operational telemetry reports connections, disconnects, resume outcomes, notifier lag, and reconciliation failures without high-cardinality metric labels.

**Done when:** users receive secure live status notifications, recover from missed or repeated events through authoritative snapshots, and see correct balances and safe outcomes.

## Phase 5 — Stale-submitted reaper and admin long polling

### Prerequisites

- [ ] The SSE hard stop gate is green.
- [ ] All four slices have proven duplicate safety because reaper republication intentionally permits duplicates.
- [ ] Staleness threshold exceeds producer delivery timeout plus expected commit and scheduler jitter.

### Reaper — Domain

- [ ] Define candidate selection as only `submitted` rows older than the configured threshold.
- [ ] Reconstruct the original envelope and exact original key from authoritative transaction data.
- [ ] Define bounded claim, publish, post-ack guard, failure release, and concurrent-reaper decisions.

### Reaper — DB

- [ ] Implement indexed, bounded stale scans with concurrency-safe claiming or guarded coordination.
- [ ] Ensure multiple reaper instances cannot create an avoidable publication storm.
- [ ] After broker acknowledgement, guard `submitted → pending` and treat a zero-row result as a reload-and-observe outcome, never a forced transition.
- [ ] On publication failure, leave the row `submitted` and make it eligible for a later bounded pass.
- [ ] Never release a reservation merely because a transaction is old.

### Reaper — Process and operations

- [ ] Implement an independently runnable scheduled reaper using its owned settings and shared producer adapter.
- [ ] Publish the same `request_id`, type, submission timestamp, and key used by the API.
- [ ] Expose liveness, readiness, one-active-scheduler or leadership evidence, structured logs, scan metrics, oldest-candidate age, guarded no-ops, and alerts.
- [ ] Start the reaper only after schema, topics, producer, and worker recovery path are healthy.
- [ ] Stop accepting new work before shutdown, then let the active bounded scan or publish attempt finish safely.

### Admin long polling — Domain

- [ ] Define a frozen admin transaction projection and opaque cursor value for `(updated_at, id)`.
- [ ] Define ascending keyset semantics, limit bounds, timeout bounds, and exact timeout response behavior.

### Admin long polling — DB

- [ ] Query `WHERE (updated_at, id) > (:updated_at, :id) ORDER BY updated_at ASC, id ASC` using the supporting index.
- [ ] Return newly inserted rows and later versions of the same row as `updated_at` advances.
- [ ] Wait without holding an open transaction or consuming unbounded database connections.
- [ ] Prevent missed wakeups between the initial query and wait mechanism, then re-query PostgreSQL before responding.
- [ ] Keep Kafka entirely outside the admin read path.

### Admin long polling — API

- [ ] Implement `GET /admin/transactions` with development admin authorization, optional opaque `cursor`, `limit` from 1 through 100, and `timeout_seconds` from 0 through 30.
- [ ] Return an initial page immediately when no cursor is supplied.
- [ ] Return available rows immediately; otherwise wait only up to the requested bound.
- [ ] Encode the last returned item in `next_cursor`; on timeout return empty items and the input cursor; return `null` only for an empty initial result.
- [ ] Return `422 VALIDATION_ERROR` for malformed cursors without leaking decoder detail.
- [ ] Cancel waits and release resources promptly when the client disconnects.

### Admin long polling — UI

- [ ] Start from an initial page, process rows in returned order, and upsert by transaction `id` or `request_id`.
- [ ] Advance the cursor only after every returned row has been processed.
- [ ] Reissue the next request immediately after a response or healthy timeout.
- [ ] Retry transient transport failures with bounded backoff; distinguish healthy timeout from error.
- [ ] Replace an existing row only with a newer `updated_at` and never append duplicate lifecycle versions as separate transactions.
- [ ] Stop polling and clear sensitive state when admin authorization is removed or the development-only page is disabled.

### Smoke check

- [ ] Stop the API after a `submitted` commit and before publish; watch the reaper republish and the command reach one terminal state.
- [ ] Inspect reaper logs to confirm stale `pending` and `in_progress` rows are never selected and aged ones raise alerts.
- [ ] Exercise admin long polling: load the initial page, submit transactions, and confirm the UI upserts one current row per transaction as statuses advance.
- [ ] Confirm a malformed cursor returns `422`, admin authorization is enforced, and the admin page remains development-only.

### Migration and rollback concerns

- [ ] Require the Phase 2 stale-scan and cursor indexes before enabling reaper or long polling.
- [ ] Stop the reaper before application rollback, restore, or database repair.
- [ ] Do not reset admin cursors server-side during rollback; clients perform bounded resynchronization from PostgreSQL when compatibility is lost.
- [ ] Coordinate database restore with stopped API intake, worker, and reaper plus an explicit Kafka offset and retained-command decision.

### Producer-gap and admin-update hard stop gate

- [ ] Every API crash window exercised in the smoke check is either terminally recorded or recovered by stale-`submitted` republication with no double application.
- [ ] The reaper never touches a non-`submitted` transaction and remains safe with multiple instances.
- [ ] Admin long polling observes creation and every later status version without skipped ordered updates, while the UI maintains one current row per transaction.

**Done when:** stale `submitted` work is recovered safely, stale later states are alerted rather than republished, and administrators observe all transaction updates through bounded PostgreSQL long polling.

## Final operations, documentation, and release gate

No phase or slice is release-complete until this gate is green. A partially green checklist is not approval to ship.

### Operations and documentation

- [ ] Document exact independently runnable commands for Kafka bootstrap, migration, API, worker, reaper, frontend, and local shutdown.
- [ ] Document startup order: PostgreSQL, Kafka/topics, migration, API, worker, reaper, frontend.
- [ ] Document graceful shutdown order that stops intake, closes SSE, stops reaper scans, drains or preserves worker work, then stops Kafka and PostgreSQL.
- [ ] Document readiness and degradation behavior for API, worker, reaper, SSE, and admin polling.
- [ ] Add structured logs correlated by `request_id` across submit, publish, worker, retry, terminal commit, DLQ, reaper, SSE, and admin updates.
- [ ] Add bounded-cardinality metrics and owned alerts for producer failures, aged statuses, lag, crash loops, rebalances, DLQ growth/failure, lock mismatch, constraints, readiness, SSE degradation, and admin polling errors.
- [ ] Add and exercise runbooks for broker outage, stale `submitted`, stale `pending`, stale `in_progress`, worker crash, lock reconciliation, poison messages, controlled DLQ replay, SSE degradation, admin cursor failure, migration failure, backup/restore, and data-integrity incidents.
- [ ] Verify backup checksums and an isolated restore drill before any persistent-environment migration.
- [ ] Record dependency/image compatibility and vulnerability review, topic retention/replication/ACL policy, and partition-change policy.
- [ ] Keep all five Version 2 contracts and the Version 2 README consistent with the implemented behavior and commands.

### Full verification

- [ ] Run `uv run ruff check .` from `backend/`.
- [ ] Run `uv run ruff format --check .` from `backend/`.
- [ ] Run `uv run mypy app` from `backend/`.
- [ ] Run `yarn lint`, `yarn typecheck`, and `yarn build` from `frontend/`.
- [ ] Run a clean-environment smoke check covering authentication, all four `202` submissions, immediate debit locks, success settlement, failure release, worker restart redelivery, DLQ visibility, reaper recovery of a stuck `submitted` row, SSE reconnect, and admin cursor updates, and confirm all observed data appears valid.

### Future: automated tests and CI

- [ ] Deferred: backend pytest suites (unit, PostgreSQL integration, migration, Kafka integration, end-to-end, recovery), frontend Vitest, soak testing, and the CI pipeline enforcing them. Scope and reintroduction order are defined in [TECHNICAL_REQUIREMENTS.md](TECHNICAL_REQUIREMENTS.md) §15.

### Release and rollback

- [ ] Provision and verify topics before enabling producers, worker, or reaper.
- [ ] Apply and verify migrations before starting code that depends on Version 2.
- [ ] Start components in dependency order and verify readiness before opening mutation intake.
- [ ] Observe the release soak period and obtain an explicit go/no-go decision.
- [ ] Stop mutation intake and reaper first during rollback; decide separately whether a compatible worker drains accepted work.
- [ ] Allow application rollback only when schema, statuses, envelope, topics, locks, and already-written data remain compatible.
- [ ] Use a forward fix or approved restore when compatibility is not provable.
- [ ] After rollback or restore, rerun readiness, integrity, lock reconciliation, duplicate-safety, and compatible smoke checks before reopening traffic.

### Final hard stop gate

- [ ] Every phase and transaction-slice gate is green in order.
- [ ] Schema compatibility, status guards, duplicate safety, key ordering, reserve/settle/release, crash recovery, producer-gap recovery, retry/DLQ, SSE security/reconnect, and admin cursor/upsert evidence is retained.
- [ ] All quality commands pass from a clean checkout.
- [ ] Operations, migration, backup/restore, release, rollback, and incident procedures have been exercised rather than merely written.
- [ ] No known invariant violation, cross-user disclosure, unbounded retry, silent message loss, stuck reservation, or skipped admin update remains open.

**Version 2 is done when:** all four wallet mutations return `202 Accepted` with `request_id`; debit funds reserve at submission and settle or release atomically; `wallet` commands preserve required key order; the worker processes at least once without double-applying assets; exhausted failures reach `wallet_dlq`; the reaper safely closes the `submitted` publication gap; users reconcile secure live statuses over SSE; administrators receive every database-backed status update through `(updated_at, id)` long polling; and every operational, migration, security, build, and smoke-check gate above is green.
