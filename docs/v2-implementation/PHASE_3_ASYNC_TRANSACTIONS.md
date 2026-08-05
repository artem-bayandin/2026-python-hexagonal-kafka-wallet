# Phase 3 — Shared submission/worker skeleton and transaction slices

Build the shared asynchronous machinery once, then convert the four wallet mutations one at a time in the strict order `deposit → withdrawal → exchange → transfer`. Within every slice work in the strict order **Domain → DB → API/worker → UI**. Do not start a slice while the prior slice's gate is red.

Order of work:

1. `shared-skeleton` (submit orchestrator, consumer/dispatcher, retry loop, DLQ path)
2. `slice-1-admin-deposit`
3. `slice-2-user-withdrawal`
4. `slice-3-user-exchange`
5. `slice-4-user-transfer`

Phase 3 is an integration milestone, not a production-release point: until the Phase 5 reaper gate is green, a crash in the database-to-Kafka publication gap can leave `submitted` work requiring explicit operational containment.

## Current implementation status

- **Not started.** Phase 1 (Kafka infrastructure) and Phase 2 (async schema and state machine) are complete: topics exist, settings validate, the producer adapter is proven, the schema carries `request_id`/`status`/`error`/`updated_at`/`locked_amount`, and guarded transition/reservation repository primitives exist.

Canonical behavior is defined by [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §4/§7–§12, [API_CONTRACT.md](../v2/API_CONTRACT.md) §Asynchronous submission, [CONFIGURATION.md](../v2/CONFIGURATION.md) §5–§6, and [IMPLEMENTATION_STEPS.md](../v2/IMPLEMENTATION_STEPS.md) §Phase 3.

## Purpose

Prove one common asynchronous path — submit, publish, consume, execute, terminal state, duplicate safety, failure handling — and then run all four transaction types through it with the smallest useful UI adaptation per slice.

## Scope

### In scope

- Shared submission orchestrator returning `202 Accepted` with `{request_id}`.
- Worker consumer lifecycle, envelope validation, type dispatcher, three-attempt retry loop, DLQ publication, source-offset acknowledgement ordering.
- Slice-by-slice conversion of `POST /admin/deposits`, `POST /me/withdrawals`, `POST /me/exchanges`, `POST /me/transfers`.
- UI `202` handling, `request_id` reconciliation, total/locked/spendable balance display.

### Out of scope

- SSE live updates (Phase 4) — Phase 3 UI uses authoritative transaction refresh after submission.
- Stale-`submitted` reaper and admin long polling (Phase 5).
- Automated tests (deferred per [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §15).

## Architecture rules

- Submission and execution are separate use cases; neither transport adapter owns financial logic. Kafka payload data never overrides PostgreSQL state.
- Submission output is the durable `request_id`, generated once and never replaced during retry, redelivery, republication, or replay.
- The envelope carries exactly `{request_id, type, submitted_at}`; keys are the submitting user UUID string (user commands) or the literal `admin` (deposits); publication without a key is impossible.
- Direct publication after commit: validate → reserve + insert `submitted` in one transaction → commit → publish → guard `submitted → pending` after acknowledgement (new transaction) → `202`. Never hold a PostgreSQL transaction during Kafka I/O or backoff.
- On definitive bounded publication failure: guard `submitted → failed`, release any reservation, and store a safe error — atomically, in one transaction.
- Worker: validate envelope → load by `request_id` → compare stored type → claim `pending → in_progress` → execute with deterministic wallet locks → commit wallet mutation + settlement/release + terminal status in one transaction → acknowledge the source record.
- Exactly three local attempts for retryable failures with bounded backoff while status remains `in_progress`; poison input (malformed envelope, unknown type, irreconcilable mismatch) fails terminally without pointless retries.
- Exhausted or poison failure: publish original key/envelope plus safe context to `wallet.dlq`, await acknowledgement, then commit safe terminal failure + reservation release, then acknowledge the source record. If DLQ publication fails, leave the source record unacknowledged and alert. Never commit `failed` before DLQ acknowledgement (no durable DLQ marker exists).
- Keep each converted route behind an explicit deployment boundary so old synchronous and new asynchronous execution cannot both apply the same submission.

## Shared skeleton

### Prerequisites

- [ ] Phase 2 schema compatibility hard stop gate is green.
- [ ] Kafka, PostgreSQL, topics, migration revision, process settings, and permissions pass readiness.
- [ ] Retry classifications and safe error mappings (table below) are reviewed before worker behavior is implemented.

### Domain

Create `backend/app/domain/use_cases/submission/__init__.py` and `backend/app/domain/use_cases/submission/submit_transaction.py` — the shared submission use case parameterized per type by the slices:

```python
@dataclass(frozen=True, slots=True)
class SubmissionResult:
    request_id: UUID

# Handler responsibilities:
# 1. run the slice-specific validation + persistence (returns request_id, partition key, envelope)
# 2. publish via CommandPublisher port
# 3. guard submitted → pending on acknowledgement, or submitted → failed (+ release) on definitive failure
# 4. return Result[SubmissionResult] — 202 is an API concern; the handler returns the durable request_id either way
```

Create `backend/app/domain/use_cases/execution/__init__.py` with the shared execution contract: `ExecuteCommand` carries explicit identifiers only (`request_id`, stored type) — never request-scoped authentication state. Define the dispatch and failure decisions next to the code:

| Situation | Decision |
| --- | --- |
| Terminal transaction observed | acknowledge and skip; no wallet mutation |
| Transaction still `submitted` | defer/safe-retry; never acknowledge as a duplicate |
| Guarded update affects zero rows | reload and observe; never force a transition |
| Retryable infrastructure failure (DB connection, broker hiccup) | retry up to 3 local attempts with bounded backoff |
| Poison input (malformed envelope, unknown type, irreconcilable type mismatch, missing transaction after bounded visibility delay) | terminal failure path; no repeated attempts; no balance mutation |

Define shared ports in `backend/app/domain/ports/`: reuse `CommandPublisher` (Phase 1); add `StatusNotifier` as a placeholder-free minimal port only if Phase 4 needs it now — otherwise leave notifications to Phase 4.

### DB

Compose the Phase 2 primitives into the shared flows in `backend/app/db/repositories/transaction_command_repository.py`:

- `insert_submitted(...)` — insert one `submitted` transaction with unique `request_id`, immutable terms, resolved identities, and (for debit types) the conditional reservation in the same session transaction. Commit before any Kafka call.
- Post-ack `mark_pending_if_submitted` in a new transaction.
- `fail_after_publication(request_id, safe_error)` — `submitted → failed` with atomic reservation release.
- `claim_for_execution(request_id)` — worker claim; also used for `in_progress` recovery inspection under row lock.
- `load_for_execution(request_id)` — row-locked state inspection after claim.

Add the bounded visibility delay helper for the worker's `submitted`-race decision: when the consumed transaction is still `submitted`, re-check after a short bounded delay (settings-driven constant, not a new env var) before classifying.

### API and worker

**API side** — create `backend/app/api/executors/submission.py`, the shared submission orchestrator used by all four routes:

```python
# Orchestration per request:
# async with write_session.begin():  # one PostgreSQL transaction
#     outcome = await submission_handler.validate_and_persist(command)   # slice-specific
# # commit before any Kafka call
# try:
#     await command_publisher.publish(key=outcome.key, envelope=outcome.envelope)
# except PublicationError as exc:  # definitive bounded failure
#     async with write_session.begin():
#         await tx_repo.fail_after_publication(outcome.request_id, safe_error=exc.safe_message)
# else:
#     async with write_session.begin():
#         await tx_repo.mark_pending_if_submitted(outcome.request_id)
# return 202 with {"request_id": str(outcome.request_id)}   # also when the publication path recorded terminal failed
```

`409 INSUFFICIENT_FUNDS`, `404 USER_NOT_FOUND`, and validation errors still return synchronously from the persist step (no transaction row, no publication, no `request_id`).

**Worker side** — extend `backend/app/kafka/worker/`:

Create `backend/app/kafka/worker/consumer.py` — `AIOKafkaConsumer` on topic `wallet`, group `wallet-worker`, `enable_auto_commit=False`, session/heartbeat/max-poll from settings; manual offset commit only after the terminal database commit (and DLQ durability, on failure).

Create `backend/app/kafka/worker/dispatcher.py`:

```python
# per consumed record:
# 1. decode envelope (envelope_codec.decode); malformed → DLQ + ack
# 2. load transaction by request_id; missing after bounded visibility delay → DLQ + ack
# 3. stored type != envelope type → DLQ + ack (no mutation)
# 4. status terminal → ack (duplicate)
# 5. status submitted → bounded re-check; still submitted → safe retry/defer, never ack
# 6. claim pending → in_progress (zero rows → reload and observe)
# 7. dispatch to the slice execution handler
```

Create `backend/app/kafka/worker/retry_loop.py` — exactly `WORKER_MAX_ATTEMPTS` (= 3) attempts for retryable failures with `WORKER_RETRY_BACKOFF_MS`→`WORKER_RETRY_BACKOFF_MAX_MS` backoff; no PostgreSQL transaction held during backoff; poison classification short-circuits the loop.

Create `backend/app/kafka/worker/dlq.py` — publish original key and envelope plus safe context (`request_id`, type, safe error classification, attempt count, timestamp) to `wallet.dlq` through the Phase 1 producer adapter; await acknowledgement before the terminal database commit; on DLQ publication failure leave the source record unacknowledged and log an alert-level structured event.

Emit structured logs correlated by `request_id` for: publish attempt/ack, guard outcome, delivery, claim, retry, terminal commit, DLQ ack, source ack — without implying cross-system atomicity.

### UI

Update `frontend/src/api/walletClient.ts` and `frontend/src/api/adminClient.ts` with a shared typed submission helper:

```typescript
export interface SubmissionAccepted {
  request_id: string;
}
```

Add a shared reconciliation helper in `frontend/src/utils/transaction_status.ts` usage: after any `202`, refetch the authoritative transaction list (`GET /me/transactions` or the admin equivalent) and upsert by `request_id` using `mergeStatus`. Forms must present `202` as "accepted for processing", never as financial success. Show total, locked, and derived spendable balances (`spendableOf`) on the wallet page.

### Smoke check (skeleton)

Carry one no-op command (a staged `submitted` row of a not-yet-enabled type, or a deposit behind a disabled route flag) through: submit → publish → guarded claim → terminal handling → forced redelivery → DLQ path, watching PostgreSQL rows and logs. Restart the worker once mid-processing and confirm redelivery produces no second mutation. Send one malformed envelope and one unknown type and confirm nothing mutates and both reach `wallet.dlq`.

### Migration and rollback (skeleton)

- Keep each converted route behind an explicit boundary (a per-route executor switch); synchronous and asynchronous execution can never both apply one submission.
- Deploy migrated schema and verified topics before enabling producers or workers.
- Stop new mutation intake before rolling back a converted route; decide whether compatible workers drain or stop.
- Never deploy Version 1 synchronous mutation code over live Version 2 transactions unless schema, statuses, locks, and accepted work are demonstrably compatible.

### Shared skeleton hard stop gate

- [ ] The skeleton smoke check exercises status guards, source-offset ordering, bounded retries, DLQ publication, crash recovery decisions, and duplicate no-op behavior with a real broker and PostgreSQL without anomalies.
- [ ] No transaction type is enabled until the common failure paths are exercised.

**Done when:** the shared machinery safely carries a no-op smoke command through submit, publish, guarded claim, terminal handling, redelivery, and DLQ paths without implementing wallet-specific effects.

## Slice 1 — Admin deposit

### Prerequisites

- [ ] The shared skeleton hard stop gate is green.
- [ ] Deposit Version 1 financial semantics (mock deposit: credit user wallet, no admin debit) and recipient rules are confirmed against the running Version 1 baseline.

### Domain

Create `backend/app/domain/use_cases/submission/submit_deposit.py` — validate normalized recipient email, supported asset, precision, positive amount; resolve the recipient; persist immutable credit terms; return `{request_id, key: "admin", envelope}`. Deposit is credit-only: no reservation.

Create `backend/app/domain/use_cases/execution/execute_deposit.py` — credit-only execution against the stored terms.

### DB

- `insert_submitted` variant for deposit: resolved destination user, no reservation.
- Execution: create (if missing) or lock the destination wallet and credit it with `in_progress → succeeded` in one transaction; deterministic locks where wallet creation or concurrent deposits conflict; `failed` persists safely without touching any wallet.

### API and worker

- Convert `POST /admin/deposits` (`backend/app/api/routers/admin.py`) to the shared submission orchestrator: `202 Accepted` with `{request_id}`; development admin boundary (`X-Admin-Key`) unchanged and production exposure still prohibited.
- Publication key is the literal `admin` — all deposits map to one partition in order.
- Worker dispatches `deposit` to `execute_deposit` through the shared retry/DLQ/acknowledgement path.
- Admin transaction reads include lifecycle fields (`request_id`, `status`, `error`, `updated_at`).

### UI

- Update the development Admin deposit form (`frontend/src/pages/AdminPage.tsx`): submit → show accepted state keyed by `request_id` ("accepted for processing"), never claim success.
- After submission, refresh authoritative admin transactions and balances.
- Keep safe errors separate from internal failure detail.

### Smoke check

1. Submit a deposit through the admin UI: `202` with a `request_id`; watch the lifecycle reach a terminal state in `GET /admin/transactions`.
2. Inspect the database: destination wallet shows exactly one credit; the transaction projection looks correct.
3. Repeat the same submission flow once after a worker restart: no second credit.
4. Confirm admin authorization is required and deposits land on the single `admin` partition in order (consumer output shows key `admin`, one partition, ascending offsets).

### Migration and rollback

- Disable the synchronous deposit executor when the asynchronous route is enabled.
- Preserve accepted deposit work during deployment and rollback; do not reopen intake until compatible workers are available.
- Rollback must never run a synchronous deposit against an already accepted Version 2 transaction.

### Deposit hard stop gate

- [ ] The deposit smoke check passes submission, `admin` key/order, lifecycle to terminal, exactly one credit on inspection, and UI acceptance behavior.
- [ ] All shared and deposit-specific quality checks pass (`ruff`, `mypy`, `yarn lint/typecheck/build`).

**Done when:** admin deposits execute only in the worker, return `202` with `request_id`, preserve admin order, and credit exactly once.

## Slice 2 — User withdrawal

### Prerequisites

- [ ] The deposit hard stop gate is green.
- [ ] Withdrawal accounting (debit user, credit matching `admin_wallets` row), and lock ordering (user wallet then admin wallet) are explicit and reviewed.

### Domain

Create `backend/app/domain/use_cases/submission/submit_withdrawal.py` — validate asset/precision/positive amount; conditionally reserve against spendable (`amount - locked_amount`) and insert `submitted` atomically; zero affected reservation rows → `409 INSUFFICIENT_FUNDS` with no transaction and no publication.

Create `backend/app/domain/use_cases/execution/execute_withdrawal.py` — success settlement: decrement user `amount` and `locked_amount`, credit the matching admin wallet; guarded failure release: decrement only `locked_amount`.

### DB

- Reserve + insert `submitted` in one transaction.
- Lock transaction, user wallet, and admin wallet in deterministic order (user wallet by `id`, then `admin_wallets` by `currency_id`).
- Commit settlement + `succeeded` atomically; commit release + safe error + `failed` atomically for publication or execution failure.
- Concurrent withdrawals cannot reserve more than spendable funds (conditional update guard).

### API and worker

- Convert `POST /me/withdrawals` (`backend/app/api/routers/wallet.py`) to authenticated `202 Accepted` with `{request_id}` via the shared orchestrator.
- Publish with the submitting user UUID key.
- Execute only the immutable stored terms through the shared retry, DLQ, and acknowledgement path.
- `GET /me/balances` returns `amount` and `locked`; `GET /me/transactions` returns lifecycle fields.

### UI

- Update the withdrawal form for `202` and reconcile by `request_id`.
- Display total, locked, and derived spendable distinctly.
- Refresh authoritative balances and history after terminal observation available in this phase (manual/poll refresh).
- Show synchronous `INSUFFICIENT_FUNDS` separately from later terminal failures.

### Smoke check

1. Submit a withdrawal: `202`; balance read immediately shows the reservation (`locked` increased); database shows terminal settle or release.
2. Submit a withdrawal exceeding spendable funds: `409 INSUFFICIENT_FUNDS`, no transaction row, nothing published.
3. Repeat a submission after a worker restart: funds are not debited twice.
4. Two rapid withdrawals for one user: order preserved on the user's partition; no overspend.

### Migration and rollback

- Disable the synchronous withdrawal executor when the asynchronous route is enabled.
- Reconcile outstanding locks before rollback; never run code that ignores `locked_amount`.
- Stop intake and choose a compatible drain-or-stop policy for accepted withdrawals.

### Withdrawal hard stop gate

- [ ] The withdrawal smoke check covers reserve, ordered worker execution, settle/release, restart redelivery without double debit, `202`, balance projection, and UI spendable behavior.
- [ ] Lock reconciliation on inspection reports no mismatch after the smoke scenarios.

**Done when:** withdrawals reserve synchronously, execute asynchronously, settle or release atomically, and cannot double-debit or over-reserve.

## Slice 3 — User exchange

### Prerequisites

- [ ] The withdrawal hard stop gate is green.
- [ ] Both exchange directions, destination precision, exact 1:1 representability, and deterministic two-wallet locking are explicit and reviewed.

### Domain

Create `backend/app/domain/use_cases/submission/submit_exchange.py` — validate supported distinct assets, positive amount, source and destination precision, exact 1:1 representability, spendable funds; record immutable source and destination terms before publication.

Create `backend/app/domain/use_cases/execution/execute_exchange.py` — settlement: decrement source `amount` and `locked_amount`, credit destination `amount` at 1:1; guarded source-reservation release on terminal failure.

### DB

- Reserve the source and insert `submitted` atomically.
- Lock source and destination wallets in deterministic identity order (`ORDER BY id ASC`), independent of exchange direction.
- Commit both wallet mutations, settlement, and `succeeded` in one transaction; commit release + `failed` atomically without changing destination funds.
- Opposite-direction concurrent exchanges neither deadlock nor overspend.

### API and worker

- Convert `POST /me/exchanges` to authenticated `202 Accepted` with `{request_id}`; publish with the submitting user UUID key.
- Worker revalidates persisted invariants without replacing immutable terms from the envelope; shared retry/DLQ/source-acknowledgement/safe-error behavior.

### UI

- Update the exchange form for `202` and reconcile by `request_id`.
- Prevent same-asset submission client-side (server still returns `422 SAME_ASSET`); display precision errors safely.
- Show the reservation immediately through authoritative balances; refresh both assets after terminal success.

### Smoke check

1. One exchange in each direction: source settle and destination credit are exact, no rounding.
2. Same-asset submission and insufficient spendable funds are rejected safely.
3. Repeat a submission after a worker restart: source not settled twice, destination not credited twice.
4. An exchange following a withdrawal for the same user preserves per-user order.

### Migration and rollback

- Disable the synchronous exchange executor when the asynchronous route is enabled.
- Reconcile source locks and both asset balances before rollback.
- Never deploy code that can reinterpret stored exchange terms or silently round them.

### Exchange hard stop gate

- [ ] The exchange smoke check covers exact money semantics, deterministic locking, reserve/settle/release, restart redelivery safety, ordered execution, `202`, and UI reconciliation.
- [ ] Withdrawal and deposit smoke behavior remains intact.

**Done when:** both exchange directions execute exactly once from immutable stored terms with no rounding, deadlock, overspend, or leaked reservation.

## Slice 4 — User transfer

### Prerequisites

- [ ] The exchange hard stop gate is green.
- [ ] Recipient resolution, self-transfer rejection, same-asset semantics, and sender/recipient lock ordering are explicit and reviewed.

### Domain

Create `backend/app/domain/use_cases/submission/submit_transfer.py` — validate normalized recipient email, existing recipient, non-self target, supported asset, precision, positive amount, spendable funds; resolve and record the recipient and immutable same-asset terms before publication.

Create `backend/app/domain/use_cases/execution/execute_transfer.py` — revalidate recipient consistency during execution without changing recorded terms; settlement from sender reservation to recipient credit; guarded release on terminal failure.

### DB

- Resolve + record recipient, reserve sender funds, insert `submitted` atomically.
- Lock sender and recipient wallets in deterministic identity order (`ORDER BY id ASC`).
- Commit sender `amount`/`locked_amount` decrement, recipient credit, and `succeeded` atomically; commit release + `failed` atomically.
- Reciprocal concurrent transfers do not deadlock, lose updates, or create funds.

### API and worker

- Convert `POST /me/transfers` to authenticated `202 Accepted` with `{request_id}`; publish with the submitting sender UUID key — recipient identity never replaces the partition key.
- Execute through the shared retry, DLQ, acknowledgement, safe-error, and redelivery paths.
- Preserve user-history ownership and transfer `direction` (`in`/`out`) rules for sender and recipient views.

### UI

- Update the transfer form for `202` and reconcile by `request_id`.
- Keep recipient selection email-based, prevent self-transfer, display safe synchronous and terminal errors.
- Refresh sender balances and relevant transaction history after terminal success.

### Smoke check

1. One transfer: sender settle, recipient credit, correct `direction` in both users' histories.
2. Missing recipient (`404 USER_NOT_FOUND`), self-transfer (`422 TRANSFER_TO_SELF`), and insufficient spendable funds (`409`) are rejected safely.
3. Repeat a submission after a worker restart: sender not debited twice, recipient not credited twice.
4. One authenticated user cannot read another user's unrelated transactions.

### Migration and rollback

- Disable the synchronous transfer executor when the asynchronous route is enabled.
- Reconcile sender locks and both wallets before rollback.
- Preserve already resolved recipients and accepted work; never reconstruct identity from a mutable client payload during recovery.

### Transfer hard stop gate

- [ ] The transfer smoke check covers sender-key order, deterministic cross-user locks, ownership, reserve/settle/release, restart redelivery safety, `202`, and UI reconciliation.
- [ ] All four transaction-slice smoke checks pass together.

**Done when:** all four transaction types use one proven asynchronous path, and transfer completes the sequence without regressing earlier gates.
