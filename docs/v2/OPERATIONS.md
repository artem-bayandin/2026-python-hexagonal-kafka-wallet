# Version 2 operations and release contract

## 1. Purpose and authority

This document is the canonical operations, recovery, migration, backup, release, and rollback contract for Version 2. It applies the architecture in [README.md](README.md) and [TECHNICAL_REQUIREMENTS.md](TECHNICAL_REQUIREMENTS.md) and inherits unchanged Version 1 practices from [Version 1 operations](../v1/OPERATIONS.md).

PostgreSQL is the source of truth for transaction state, financial terms, balances, and locks. Kafka transports commands; Kafka offsets, SSE events, frontend state, and administrator polling responses are not authoritative financial records.

Operational action must preserve the Version 2 lifecycle and idempotency boundary. The reaper republishes only stale `submitted` transactions. Operators must never blindly republish `pending` or `in_progress` transactions. Every controlled replay preserves the original Kafka key and `request_id` and passes through the same guarded transaction-state and wallet-row checks as ordinary delivery.

For exhausted or poison worker failures, `wallet_dlq` acknowledgement must precede the database commit of terminal `failed` and lock release, and both must precede acknowledgement of the source record. Version 2 has no persisted DLQ-publication marker, so reversing the first two steps can silently lose the DLQ record after a crash. A crash after DLQ acknowledgement may create a duplicate DLQ record on redelivery; that is safe and preferable to loss.

## 2. Current and target status

Version 1 is the current implementation. The repository has the FastAPI application, React frontend, PostgreSQL 18.4 Compose service, Alembic migrations, authentication, admin wallet flow, and synchronous user wallet flows. It does not currently have a Kafka service, Kafka client dependency, command-worker entry point, reaper entry point, Version 2 schema, SSE stream, Version 2 readiness checks, or complete automated CI.

Version 2 is a target contract, not a statement about currently runnable software. Version 2 is operationally complete only after PostgreSQL and Kafka infrastructure, migrations, API producer, worker, reaper, SSE notifier, administrator long polling, telemetry, runbooks, and release gates in this document are implemented and verified.

The target transaction lifecycle is `submitted → pending → in_progress → succeeded|failed`. The API creates `submitted`, changes it to `pending` only after Kafka acknowledges publication, or changes it to `failed` after a definitive bounded publication failure. The worker changes `pending` to `in_progress` and commits either terminal state with the financial mutation or lock release. Terminal states never transition.

## 3. Component dependency and ownership

| Component | Operational responsibility | Hard dependencies |
| --- | --- | --- |
| PostgreSQL | Authoritative transactions, balances, locks, users, and cursors | Durable storage |
| Kafka | `wallet` command transport and `wallet_dlq` isolation | Broker storage, configured topics |
| Alembic migration step | Brings PostgreSQL to the schema required by the release | Healthy PostgreSQL, release artifacts |
| API | HTTP submission and queries, Kafka publication, SSE endpoint | Migrated PostgreSQL; Kafka for mutation-submission readiness |
| Command worker | Consumes `wallet`, executes guarded commands, publishes exhausted failures to `wallet_dlq` | Migrated PostgreSQL, Kafka, topics, `wallet_worker` group configuration |
| Reaper | Scans stale `submitted`, republishes the same command, then guards `submitted → pending` after acknowledgement | Migrated PostgreSQL, Kafka, command topic, scheduler or leadership mechanism |
| Frontend | User and admin browser interface | Ready API; working SSE and admin polling for live updates |

The API, worker, and reaper are independently deployable processes. The worker and reaper must not depend on request-scoped authentication context. The frontend must reconcile from database-backed HTTP queries and must not treat an SSE event or polling response as final authority without transaction identity and status checks.

## 4. Local startup

### 4.1 Current Version 1

Install backend dependencies once:

```sh
cd backend
uv sync --all-groups
```

Start PostgreSQL from the repository root:

```sh
docker compose --env-file backend/.env up -d postgres
```

Apply migrations, then start the API from `backend/`:

```sh
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
```

Install frontend dependencies once and start the frontend from `frontend/`:

```sh
corepack enable
yarn install --immutable
yarn dev
```

These are current repository commands. They start Version 1 only.

### 4.2 Version 2 target order

The required local startup order is:

1. Start PostgreSQL and wait for its Compose health check to pass.
2. Start Kafka and wait for broker connectivity and required topic metadata for `wallet` and `wallet_dlq`.
3. Apply the reviewed Alembic migration from the Version 1 head and verify the database revision.
4. Start the API and wait for liveness and readiness.
5. Start the command worker and wait for database, broker, topic, and consumer-group readiness.
6. Start the reaper only after the worker is available, then verify its scheduler or leader and one bounded scan.
7. Start the frontend and verify API access, SSE connection, and administrator polling as applicable.

The repository does not yet implement Kafka, worker, or reaper services or executable entry points, so this document does not invent launch commands for them. Their implementation must add explicit, independently runnable commands and update this section in the same change. Until then, a claimed local Version 2 startup is unsupported.

Do not run a worker or reaper against a database whose migration is behind the process's required schema. Do not start the reaper before Kafka topic metadata and the worker recovery path are healthy, because republication without consumption can amplify an outage.

## 5. Local shutdown

The graceful Version 2 shutdown order is:

1. Stop frontend-driven mutation intake and remove the API from readiness so no new commands are accepted.
2. Close SSE streams cleanly and stop the API after active HTTP handlers finish or roll back.
3. Stop the reaper and wait for its active bounded scan or publication attempt to complete.
4. Stop worker polling, allow bounded in-flight work to commit, and leave any unacknowledged Kafka record unacknowledged for redelivery.
5. Stop Kafka only after producers and consumers have disconnected and offsets or unacknowledged work are in a known state.
6. Stop PostgreSQL last, after API, worker, and reaper database transactions and connections have closed.

For the current Version 1 local stack, interrupt `yarn dev` and Uvicorn, then stop PostgreSQL from the repository root:

```sh
docker compose --env-file backend/.env stop postgres
```

A forced worker termination must not be treated as successful processing. On restart, Kafka redelivery and PostgreSQL guards must decide whether to resume, skip a terminal transaction, or alert on an unresolved `in_progress` transaction.

## 6. Health, readiness, and degradation

Liveness answers only whether a process is running. Readiness answers whether the component can perform its assigned role without knowingly accepting work it cannot safely handle. Readiness probes must be bounded and must not mutate financial state.

| Component | Liveness | Readiness |
| --- | --- | --- |
| PostgreSQL | Container or process is running | `pg_isready` succeeds and required database is reachable |
| Kafka | Broker process is running | Broker metadata is reachable; `wallet` and `wallet_dlq` exist with expected configuration |
| Migration step | Process is active while running | Successful exit and database revision equals the release-required head |
| API | `GET /health/live` returns `200` | `GET /health/ready` returns `200` only when PostgreSQL, required schema, and dependencies required for accepted mutation submissions are usable; otherwise `503` |
| Command worker | Worker process and polling loop are alive | PostgreSQL and Kafka are reachable, topics resolve, group configuration is valid, and the worker can poll without a fatal error |
| Reaper | Reaper process or scheduler loop is alive | PostgreSQL and Kafka are reachable, required schema and topic resolve, and exactly the configured scheduling or leadership mechanism is active |
| Frontend | Development server or deployed static site responds | Assets load and configured API origin is reachable; API, SSE, and admin polling degradation is displayed rather than hidden |

The current API implements `GET /health/live` and a PostgreSQL-only `GET /health/ready`. Version 2 must extend readiness before mutation traffic is enabled. Readiness failure is not permission to kill a process immediately; orchestration must first remove it from new traffic and allow graceful shutdown.

SSE failure may be reported as a degraded user-notification capability while database-backed queries remain available. Administrator long-poll timeout with a successful empty response is healthy; repeated transport, authentication, database, or cursor errors are degraded.

## 7. Structured logs

All API, producer, worker, reaper, SSE, and administrator-polling logs must be structured and timestamped in UTC. A transaction trace uses `request_id` as its stable correlation identity.

Relevant events include component, environment, event name, severity, `request_id`, transaction type, safe status, route, HTTP status, Kafka topic, partition, offset, record key class, consumer group, retry number within the current delivery, duration, and safe error classification. Include user or wallet identifiers only where operationally necessary and permitted; do not use raw personal data as a default correlation field.

Log state-transition outcomes, including guarded no-ops, without logging financial secrets or unrestricted payloads. Distinguish publish attempted, publish acknowledged, state changed to `pending`, delivery received, execution claimed, terminal database commit, DLQ acknowledged, and original offset acknowledged so incident timelines do not infer atomicity where none exists.

Never log OTPs, JWTs, admin keys, database or Kafka credentials, connection strings, full unexpected exception text in client-visible fields, or unredacted command payloads. DLQ error context and stack traces remain access-controlled and must use safe classification where exported.

## 8. Metrics and alerts

Metrics must cover:

- HTTP request count, latency, response class, submission result, and readiness state;
- producer send latency, acknowledgements, retries, timeouts, and failures by topic and operation type;
- transaction count and oldest age by `submitted`, `pending`, and `in_progress`, plus terminal outcomes by type;
- reaper candidates, claimed rows, publication attempts, acknowledgements, guarded no-ops, failures, scan duration, and oldest eligible age;
- worker consumed records, throughput, processing latency, local retry attempts, retry exhaustion, rebalances, offset-acknowledgement failures, and failures by safe class;
- consumer lag by topic, partition, and group;
- DLQ publication success and failure, DLQ ingress, retained depth or lag, and oldest record age;
- lock totals and reconciliation mismatches by currency without user or `request_id` metric labels;
- SSE active connections, connection duration, disconnects, reconnect/resume outcomes, notifier lag, and reconciliation-query failures;
- administrator long-poll duration, timeout responses, rows returned, cursor failures, client retry rate, and database query errors;
- PostgreSQL connectivity, pool saturation, transaction rollback, deadlock, constraint failure, and migration revision mismatch.

Do not place `request_id`, user ID, transaction ID, wallet ID, raw error text, or Kafka offset in metric labels because they create unbounded cardinality. Keep those values in correlated logs.

Alerts must have environment-specific thresholds and an owner. At minimum, alert on aged `submitted`, stale `pending` with lag or worker outage, stale `in_progress`, repeated reaper publication failure, producer failure, sustained consumer lag, worker crash loop or rebalance storm, DLQ growth, DLQ publication failure, readiness failure, migration mismatch, database pool exhaustion, lock mismatch, constraint or invariant violation, attempted negative balance, SSE notifier degradation, and sustained administrator polling errors.

An alert on stale `pending` or `in_progress` must direct operators to investigation, not automatic republication. Alert annotations should link to the matching runbook section and dashboards.

## 9. Database migration contract

Every schema change uses a reviewed Alembic revision. Generate a candidate from `backend/`, review all generated DDL manually, and exercise the exact upgrade from the current Version 1 head:

```sh
uv run alembic revision --autogenerate -m "<summary>"
uv run alembic upgrade head
```

Before release, verify legacy `completed → succeeded` migration, unique `request_id` backfill, `updated_at` backfill, status constraints, `locked_amount` constraints, stale-status indexes, and `(updated_at, id)` cursor indexes. Measure table lock behavior and expected duration against production-like data.

The release must define whether downgrade is safe after Version 2 writes exist. If statuses, locks, or request IDs cannot be represented by Version 1 code, rollback by schema downgrade is prohibited; use a forward fix or restore plan.

A failed migration keeps API, worker, and reaper code that requires the new schema disabled. Capture Alembic output and database state, determine whether the failed statement committed, and follow the documented migration recovery procedure. Never rerun or downgrade blindly.

## 10. Backup and restore

Take a logical PostgreSQL backup before every production schema migration and on a schedule matching approved recovery-point and recovery-time objectives. Use tooling compatible with the pinned PostgreSQL major version, encrypt backups, restrict access, record checksums, and store copies outside the primary database failure domain.

The deployment implementation must provide the exact environment-specific `pg_dump` and restore commands; this draft does not invent credentials, hostnames, paths, or storage destinations. A backup is not verified until a scheduled restore drill loads it into an isolated database and validates schema revision, row counts, constraints, representative transaction history, balances, and locks.

Kafka command retention is not a substitute for a PostgreSQL backup. A database restore requires a coordinated decision about Kafka offsets and retained commands: keep consumers and reaper stopped, identify the restore timestamp, determine which records may predate or postdate restored terminal commits, and rely on guarded processing during a controlled restart.

## 11. Release procedure and gates

Every release must:

1. Build from committed backend and frontend lockfiles and pinned deployment images.
2. Review dependency and image vulnerabilities and Kafka broker/client compatibility.
3. Pass backend Ruff lint and format check and strict mypy.
4. Pass frontend lint, TypeScript typecheck, and production build.
5. Verify a fresh backup and successful recent restore drill before a production schema change.
6. Apply migrations before starting code that depends on the Version 2 schema.
7. Provision and verify `wallet` and `wallet_dlq` configuration before enabling producers, worker, or reaper.
8. Start API, worker, and reaper in dependency order and verify every readiness condition.
9. Run a smoke check covering authentication, one debit command, one admin deposit, lock visibility, terminal status, balance settlement or release, SSE reconciliation, administrator cursor polling, and DLQ health, confirming the returned data appears valid.
10. Observe submission failures, stale-status age, consumer lag, worker outcomes, DLQ growth, database constraints, and readiness for the release soak period before declaring success.

The currently declared quality commands are:

```sh
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
cd ../frontend
yarn lint
yarn typecheck
yarn build
```

Automated test suites (backend pytest, frontend Vitest, Kafka integration and recovery suites) and CI are deferred to possible future steps; see [TECHNICAL_REQUIREMENTS.md](TECHNICAL_REQUIREMENTS.md) §15. Their exact invocation must be documented here when they are introduced.

## 12. Rollback

First stop new mutation intake and the reaper. Decide separately whether healthy workers should drain already accepted work or stop polling; the decision depends on whether the deployed worker remains schema- and message-compatible.

Application rollback is allowed only when the older API, worker, reaper, and frontend are compatible with the current schema, statuses, Kafka envelope, topic configuration, and already-written data. Never deploy Version 1 synchronous mutation code over a live Version 2 database merely because binaries can start.

Do not decrease Kafka partition count. Increasing partition count during rollback or incident response is also prohibited without an ordering-impact review because future records for a key may map differently.

If schema or data is incompatible, prefer a forward fix. Restore only under the approved disaster-recovery plan, with API intake, worker, and reaper stopped and with an explicit Kafka offset and replay decision. After rollback or restore, rerun readiness checks, integrity checks, and the compatible smoke check before reopening traffic.

## 13. Incident handling principles

For every incident, assign an incident lead, record UTC timestamps, stop unsafe automated actions, preserve logs and broker/database evidence, and state whether mutation intake, worker polling, and reaper scans remain enabled. Prefer reversible containment over direct data edits.

Use `request_id` to correlate the transaction row, locks, producer events, Kafka topic/partition/offset, worker events, terminal commit, DLQ record, SSE notification, and administrator observations. Never infer financial completion from an acknowledged Kafka record or committed offset alone.

Any manual database repair requires a reviewed query, transaction boundary, before-and-after evidence, peer approval, and a reconciliation report. Direct balance or lock edits during active submission or worker execution are prohibited.

## 14. Runbook: Kafka unavailable during submission

1. Confirm broker and topic readiness, producer timeout/failure rate, and API readiness; remove the API from mutation traffic if required dependencies are unavailable.
2. For each affected `request_id`, inspect PostgreSQL first. If no transaction exists, no accepted command or lock exists. If it is `failed`, confirm the safe publication error and atomic lock release. If it is `submitted`, publication outcome may be unknown.
3. Do not manually change an ambiguous `submitted` row to `pending`. Restore Kafka and let the reaper republish the same envelope and key after the configured age.
4. Confirm broker acknowledgement followed by guarded `submitted → pending`; a guarded no-op is expected if another actor already advanced the row.
5. Verify producer errors recover, stale-`submitted` age falls, locks correspond to remaining nonterminal debit transactions, and terminal failures are visible to clients.

A definitive bounded publish failure is handled by the API as `submitted → failed` with lock release. A process crash before that database update leaves `submitted`, which belongs to reaper recovery.

## 15. Runbook: worker receives a transaction still in `submitted`

1. Treat this as the expected race between Kafka delivery and the API or reaper's post-ack `submitted → pending` update, not as a duplicate or poison message.
2. Do not execute the financial mutation, acknowledge the source record, move the transaction directly to `in_progress`, or publish it to the DLQ while the row remains `submitted`.
3. Defer or retry state inspection with bounded backoff while preserving consumer heartbeats and without holding a PostgreSQL transaction open.
4. If the row becomes `pending`, continue through the normal guarded worker claim. If it becomes terminal, acknowledge and skip without mutation.
5. If it remains `submitted` beyond the bounded worker wait, leave the source record unacknowledged, emit an alert with `request_id`, and investigate the API post-ack guard and reaper health.
6. Verify that recovery produces one terminal outcome and at most one financial effect; do not force a status transition merely to advance the Kafka offset.

## 16. Runbook: stale `submitted` and reaper failure

1. Check transaction age, API producer logs, reaper liveness/readiness, scan index health, candidate count, and reaper publication failures.
2. Confirm every candidate is still `submitted` before publication. The reaper must use a bounded scan and safe row claiming or concurrency control.
3. Republish the original envelope with the original user UUID key or fixed `"admin"` key and the same `request_id`.
4. After Kafka acknowledgement, guard `submitted → pending`. If the guard affects no row, reload and record the current status; do not force it backward.
5. If publication fails, leave the transaction `submitted`, release the claim according to implementation semantics, alert, and retry only through the bounded schedule.
6. If multiple reapers caused duplicates, do not delete financial rows or rewrite Kafka history; verify that guarded worker processing produced at most one financial mutation.

The reaper must never select or republish `pending`, `in_progress`, `succeeded`, or `failed`.

## 17. Runbook: stale `pending` or consumer lag

1. Confirm worker liveness/readiness, `wallet_worker` membership, partition assignment, lag by partition, broker health, database connectivity, poison-message behavior, processing latency, and rebalance rate.
2. Identify whether lag is global, limited to one partition, or concentrated behind one record. Correlate the oldest affected record to PostgreSQL by `request_id`.
3. Do not republish the transaction. `pending` means Kafka already acknowledged the command; an extra publication can violate expected ordering and add duplicate work.
4. Restore or scale healthy workers within the topic partition limit, fix the blocking dependency or poison-message path, and allow the original record to be consumed.
5. Verify lag decreases, `pending → in_progress` guards succeed, offsets advance only after required database and DLQ outcomes, and per-key ordering remains intact.

If no corresponding Kafka record can be found after a complete broker and retention investigation, escalate for a reviewed recovery decision. Absence must not be guessed from one consumer view or from lag alone.

## 18. Runbook: stale `in_progress` or worker crash

1. Stop any crash loop and inspect the transaction row, wallet rows, database commit evidence, worker logs, record offset, group offset, and broker redelivery state.
2. If the transaction is terminal, the financial commit already decided the outcome; allow redelivery to acknowledge and skip through the terminal-state guard.
3. If it remains `in_progress`, do not blindly republish it and do not reset it to `pending`. Restore a compatible worker and let Kafka redelivery enter the documented recovery path under transaction and wallet-row locks.
4. The recovery path must inspect state after locking and may resume only a mutation that has not already committed. It must commit wallet changes and terminal status atomically.
5. If the original record is unavailable or recovery cannot prove a safe path, keep intake for the affected scope contained and escalate to reviewed manual reconciliation.
6. Confirm terminal state, exactly one financial effect, correct lock settlement or release, and safe offset handling before resolving the incident.

A worker crash can start a new local retry loop after redelivery because Version 2 has no persisted attempts counter. Monitor repeated crashes and lag rather than manufacturing an attempts value.

## 19. Runbook: lock reconciliation

1. Quiesce mutation intake, worker polling, and reaper activity for the affected users or system if a consistent snapshot cannot otherwise be obtained.
2. For each user wallet and currency, derive expected reserved debit from nonterminal withdrawal, exchange, and transfer transactions in `submitted`, `pending`, or `in_progress`. Deposits never contribute a lock.
3. Compare derived reservation to `user_wallets.locked_amount`, verify `0 <= locked_amount <= amount`, and identify terminal transactions that appear to have retained or released a lock incorrectly.
4. Correlate every mismatch to state-transition and wallet-mutation logs. Determine whether the cause is migration, duplicate failure handling, partial manual repair, or an application defect.
5. Repair only through a reviewed database transaction that locks the transaction and wallet rows, rechecks current state, and changes the minimum necessary values. Never release a lock merely because a transaction is old.
6. Re-run reconciliation, constraints, affected balance history, and a duplicate-delivery smoke check before restoring processing.

## 20. Runbook: DLQ triage and controlled replay

1. Restrict DLQ access, snapshot relevant metadata, and group records by safe failure classification, type, key, `request_id`, producer version, partition, and failure window.
2. Validate the envelope and locate the authoritative transaction. Check key semantics, stored type, current status, safe error, locks, original delivery logs, and whether the root cause is deterministic or retryable.
3. Fix or contain the root cause before replay. Exercise the exact record against a production-like environment and define batch size, rate limit, observation window, abort threshold, and owner.
4. Replay to `wallet` only through an approved tool that preserves the original record key, envelope `request_id`, type, and submission timestamp. Do not generate a new key, remove identity fields, or bypass the normal worker.
5. The worker must apply the same guarded state and wallet-row checks as ordinary delivery. Duplicate and terminal records are acknowledged and skipped without financial mutation.
6. Monitor processing result, guarded no-ops, lag, worker errors, lock invariants, balances, and renewed DLQ records after each bounded batch.

Under the canonical lifecycle, `failed` is terminal and there is no `failed → pending|in_progress` transition. Replaying a DLQ record for an already `failed` transaction therefore verifies safe deduplication but does not execute the business mutation again. A business retry must be a new authorized submission with a new `request_id`; reopening the same transaction would require a separately designed and approved state-recovery contract.

Malformed records without a usable `request_id` cannot mutate PostgreSQL. They remain evidence for producer repair and may be replayed only after producing a valid contract-compliant envelope whose identity and provenance are explicitly reviewed.

## 21. Runbook: SSE degradation

1. Check API liveness, notifier health and lag, active connections, disconnect rate, proxy buffering and timeout behavior, authentication failures, and database query latency.
2. Keep PostgreSQL-backed transaction and balance queries available when safe. SSE is a notification channel, so its degradation does not make cached frontend state authoritative.
3. Clients reconnect using the API contract, then call `GET /me/transactions`, upsert by `request_id`, ignore status regressions, and refetch `GET /me/balances` after observing or reconciling `succeeded`.
4. Verify streams are scoped to the authenticated user, event IDs resume at least once, duplicates are tolerated, and missed or expired event IDs trigger query reconciliation.
5. Resolve only after notifier lag and disconnect rate recover and a reconnect check observes a transaction without cross-user disclosure.

If authorization isolation is in doubt, disable SSE immediately while retaining safe authenticated queries and treat the event as a security incident.

## 22. Runbook: administrator polling issues

1. Distinguish a normal bounded timeout with no changes from transport, authorization, database, or cursor failure.
2. Verify the request uses the complete `(updated_at, id)` cursor or its opaque equivalent, the query orders by the same pair, and the supporting index is present.
3. Confirm every insert and status transition updates `updated_at`, responses advance the cursor only through processed rows, and the UI upserts by transaction ID or `request_id`.
4. Do not substitute UUID `id` alone, reset the cursor repeatedly, append duplicate rows, or read Kafka to fill apparent gaps.
5. On an invalid or lost client cursor, perform a bounded database-backed resynchronization according to the API contract, then resume long polling with backoff.
6. Verify a sample transaction appears at creation and on later transitions without skipped updates before closing the incident.

## 23. Runbook: data integrity incident

Data integrity incidents include negative total or spendable balance, `locked_amount > amount`, duplicate financial application, terminal status without matching settlement or release, immutable transaction-term changes, request-ID collision, cross-user SSE disclosure, or cursor history that contradicts PostgreSQL.

1. Remove the API from mutation traffic and stop reaper scans and worker polling before further state changes; keep PostgreSQL available for evidence and backup.
2. Capture a fresh protected backup, relevant transaction and wallet rows, constraints, migration revision, logs, Kafka metadata, consumer offsets, and DLQ records.
3. Define the affected users, currencies, request IDs, time range, release version, and partitions. Do not expose sensitive data in the incident channel.
4. Reconstruct each command from PostgreSQL and ordered logs, not from frontend state. Compare transaction states, wallet mutations, locks, Kafka delivery history, and terminal commits.
5. Identify the invariant and first violating write. Fix the application or migration cause before data repair.
6. Execute only a peer-reviewed repair in an explicit database transaction with deterministic row locks, preconditions, before-and-after values, and rollback instructions.
7. Reconcile all affected balances and locks, verify constraints and transaction history, run duplicate-delivery and recovery smoke checks, and obtain incident-lead approval before restarting worker, reaper, API, and frontend in normal startup order.
8. Document customer or security impact, recovery-point impact, preventive follow-ups, telemetry improvements, and follow-up ownership.

Never delete a transaction or Kafka evidence merely to make totals match. Never compensate by editing one wallet without proving the corresponding accounting effect and transaction state.

## 24. Operational definition of done

Version 2 is operationally done when documented launch commands exist for Kafka, API, worker, reaper, and frontend; startup and shutdown ordering is automated or reproducible; every component exposes the required health signals; telemetry and alerts are deployed; migration and restore drills pass; release and rollback procedures have been exercised; every runbook has an owner; and recovery walkthroughs show that duplicate delivery, process crashes, broker outages, stale states, DLQ replay, and client-notification degradation cannot double-apply assets or silently lose accepted work.
