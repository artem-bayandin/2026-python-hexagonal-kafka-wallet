# Phase 2 — Asynchronous schema and state machine

Migrate the Version 1 schema to the Version 2 transaction lifecycle and reservation model, and encode the status state machine in domain code — while mutation routes keep synchronous Version 1 execution behind an explicit compatibility boundary. Command repositories are not modified in this phase.

Work in this order:

1. `domain-state-machine`
2. `migration`
3. `api-mapping`
4. `ui-types`
5. `smoke-check`

## Current implementation status

- **Not started.** Phase 1 Kafka infrastructure is complete (broker, topics, settings, producer adapter, process shells).
- Version 1 Alembic head: `d377d8c90992` (`add_wallet_tables_version_1`). All Version 2 migrations upgrade from this exact head.

Canonical behavior is defined by [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §6/§7/§11, [API_CONTRACT.md](../v2/API_CONTRACT.md) §Shared representations, and [IMPLEMENTATION_STEPS.md](../v2/IMPLEMENTATION_STEPS.md) §Phase 2.

## Purpose

Make the Version 2 schema and state machine compatible with migrated Version 1 data, enforce invariants in PostgreSQL, and extend read models, mappers, and API/UI field mapping so Phase 3 can implement repository guards and switch mutation routes to asynchronous execution safely.

## Prerequisites

- Phase 1 hard stop gate is green.
- The exact Version 1 Alembic head and a representative legacy data set (users, wallets, `completed`/`failed` transactions) are available for the upgrade exercise.
- Lock duration and table-size assumptions are measured against production-like data before writing the migration.

## Scope

### In scope

- Alembic migration: `request_id`, Version 2 status set, `error`, `updated_at`, `user_wallets.locked_amount`, constraints, indexes.
- SQLAlchemy model columns and check constraints matching the migration.
- Domain status enum, allowed transitions, terminal/stale/duplicate decisions, reservation invariants.
- Mappers for new transaction and wallet columns.
- Internal response mapping and shared TypeScript types updated for Version 2 fields (no async behavior yet).
- Pure UI utilities for status ordering and balance display.

### Out of scope

- Any changes to command repositories or repository ports (`transaction_command_repository`, `user_wallet_command_repository`, and their domain ports) — Phase 3.
- Guarded transition, reservation, or deterministic-lock repository primitives — Phase 3.
- Switching any mutation route to asynchronous execution or `202` (Phase 3).
- Kafka publication from routes (Phase 3).
- SSE and admin long polling (Phases 4–5).
- `attempts`, outbox, inbox, processed-message, or Kafka-diagnostics columns (explicit non-goals).

## Done when

The Version 2 schema is migrated, domain types and mappers expose the new fields, API/UI serialize them against legacy rows, and PostgreSQL enforces invariants — with rollback/forward-fix policy written and approved. Repository guards are explicitly deferred to Phase 3.

## Architecture rules

- Statuses are exactly `submitted`, `pending`, `in_progress`, `succeeded`, `failed`. Allowed forward transitions: `submitted → pending`, `submitted → failed`, `pending → in_progress`, `in_progress → succeeded|failed`. Terminal states never transition.
- Every transition is a conditional update or row-locked check that verifies the expected current state; `updated_at` changes in the same statement/transaction.
- PostgreSQL stays authoritative; financial terms recorded on a transaction are immutable after submission.
- Reservation invariants use `Decimal` at existing currency precision: `locked_amount >= 0`, `amount - locked_amount >= 0`; spendable is derived (`amount - locked_amount`), never a separate mutable column.
- `error` persists only a safe client-facing failure description or code — never raw exceptions, credentials, or payloads.

## Step 1 — Domain state machine

Create `backend/app/domain/value_objects/transaction_status.py`:

```python
from enum import StrEnum


class TransactionStatus(StrEnum):
    SUBMITTED = "submitted"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


TERMINAL_STATUSES = frozenset({TransactionStatus.SUCCEEDED, TransactionStatus.FAILED})

ALLOWED_TRANSITIONS = frozenset({
    (TransactionStatus.SUBMITTED, TransactionStatus.PENDING),
    (TransactionStatus.SUBMITTED, TransactionStatus.FAILED),
    (TransactionStatus.PENDING, TransactionStatus.IN_PROGRESS),
    (TransactionStatus.IN_PROGRESS, TransactionStatus.SUCCEEDED),
    (TransactionStatus.IN_PROGRESS, TransactionStatus.FAILED),
})


def is_allowed_transition(current: TransactionStatus, target: TransactionStatus) -> bool:
    return (current, target) in ALLOWED_TRANSITIONS
```

Document the shared decisions next to this module (docstrings or a `## Shared implementation notes` update in this file):

- **Terminal-state decision:** a worker observing `succeeded`/`failed` acknowledges and skips without any wallet mutation.
- **Duplicate-delivery decision:** a guarded conditional update affecting zero rows means another actor already advanced the row; reload and observe, never force a transition.
- **Stale-delivery decision:** a redelivery of `in_progress` after worker failure may resume execution under row locks; it is never permission to re-apply a committed mutation.
- **`submitted`-race decision:** a worker consuming a transaction still in `submitted` must not treat it as a duplicate; it defers/retries safely until `pending` or a terminal state is visible (Kafka consumption can race the API's post-ack update).

Update `backend/app/domain/read_models/transaction.py` and `backend/app/domain/read_models/wallet.py` — extend the frozen read models with `request_id: UUID`, `status: TransactionStatus`, `error: str | None`, `updated_at: datetime`, and wallet `locked: Decimal`. Keep `Money`/precision semantics unchanged.

Update `backend/app/db/mappers/transaction.py` and `backend/app/db/mappers/user_wallet.py` to map the new columns.

## Step 2 — Migration

Create the migration:

```bash
cd backend
uv run alembic revision -m "version_2_async_schema"
```

Implement `backend/alembic/versions/<new_revision>_version_2_async_schema.py` against the Version 1 head (`down_revision = "d377d8c90992"`). Required DDL, in this order:

1. **`transactions.request_id`:** `ADD COLUMN request_id UUID`; backfill every legacy row (`UPDATE transactions SET request_id = gen_random_uuid() WHERE request_id IS NULL`); then `ALTER COLUMN request_id SET NOT NULL` and `ADD CONSTRAINT uq_transactions_request_id UNIQUE (request_id)`.
2. **Status set:** drop the Version 1 status check constraint; `UPDATE transactions SET status = 'succeeded' WHERE status = 'completed'` (legacy `failed` rows are retained); add the new check constraint `status IN ('submitted','pending','in_progress','succeeded','failed')`.
3. **`transactions.error`:** `ADD COLUMN error TEXT` (nullable).
4. **`transactions.updated_at`:** `ADD COLUMN updated_at TIMESTAMPTZ`; backfill `UPDATE transactions SET updated_at = created_at`; then `SET NOT NULL`. Runtime transitions update it in the same statement; do not rely on a trigger unless it is created and reviewed in this migration.
5. **`user_wallets.locked_amount`:** `ADD COLUMN locked_amount NUMERIC(<same precision/scale as amount>) NOT NULL DEFAULT 0`; add check constraints `locked_amount >= 0` and `amount - locked_amount >= 0`. Keep the existing non-negative `amount` constraint and the one-wallet-per-user-and-currency uniqueness.
6. **Indexes:**
   - stale-scan: `CREATE INDEX ix_transactions_status_created_at ON transactions (status, created_at)` (supports reaper stale-`submitted` scans by age);
   - admin cursor: `CREATE INDEX ix_transactions_updated_at_id ON transactions (updated_at, id)` (supports `WHERE (updated_at, id) > (:u, :i) ORDER BY updated_at ASC, id ASC`).
7. **Downgrade:** implement `downgrade()` only if it is provably safe before any Version 2 writes; otherwise make it raise with a documented prohibition — after incompatible statuses (`submitted`, `pending`, `in_progress`) or non-zero locks exist, downgrade requires a reviewed conversion, and the default policy is forward fix.

Manually review the generated DDL: data backfills, constraint ordering (backfill → convert → constrain), index creation lock impact (`CREATE INDEX CONCURRENTLY` is not available inside Alembic's transaction — record the lock-window decision), and transaction boundaries.

Update the SQLAlchemy models:

- `backend/app/db/models/transaction.py` — add `request_id`, `error`, `updated_at`; update the status `CheckConstraint`.
- `backend/app/db/models/user_wallet.py` — add `locked_amount` and the two check constraints.

Commands:

```bash
cd backend
uv run alembic upgrade head
uv run alembic current
```

## Step 3 — API mapping

Update `backend/app/api/schemas/wallet.py` and `backend/app/api/schemas/admin.py`:

- `BalanceItemResponse`: replace `available` with `amount` and `locked` (both formatted decimal strings).
- `TransactionItemResponse`: add `request_id`, `status` (lowercase Version 2 values), `error`, `updated_at`; drop `completed_at` if present.

Update `backend/app/api/formatting.py` / `result_mapping.py` so existing synchronous routes serialize the new fields against migrated rows (a Version 1-completed row now reads as `succeeded`).

Keep the externally active Version 1 mutation behavior (`201` synchronous execution) behind an explicit compatibility boundary — e.g. a single `_execute_synchronously` path per route clearly marked `Version 1 compatibility — replaced in Phase 3` — so Phase 3 slices replace one route at a time without mixed deployments writing statuses another live process cannot read.

**Repository boundary:** do not extend command repositories in this phase. If an existing synchronous mutation path would require guarded transitions, conditional reservation, or deterministic wallet locking, raise `NotImplementedError` (or an equivalent domain/API failure) rather than implementing partial repository work. Phase 3 owns all repository guard primitives.

Verify with:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
```

## Step 4 — UI types

Update `frontend/src/types/wallet.ts` and `frontend/src/types/admin.ts`:

```typescript
export type TransactionStatus = "submitted" | "pending" | "in_progress" | "succeeded" | "failed";

export interface BalanceItem {
  asset: string;
  amount: string;
  locked: string;
}

export interface TransactionItem {
  id: string;
  request_id: string;
  type: "deposit" | "withdrawal" | "exchange" | "transfer";
  status: TransactionStatus;
  source_asset: string | null;
  dest_asset: string | null;
  amount: string;
  error: string | null;
  created_at: string;
  updated_at: string;
  direction?: "in" | "out";
}
```

Create `frontend/src/utils/transaction_status.ts` — pure utilities:

- `statusRank(status)` — monotonic lifecycle ordering;
- `isTerminal(status)`;
- `mergeStatus(current, incoming)` — upsert by identity, replace only when `incoming.updated_at` is newer, ignore status regressions, tolerate skipped observations (e.g. `submitted` → `succeeded` observed directly);
- `spendableOf(balance)` — `amount - locked` as a decimal-string-safe computation at asset precision.

Do not expose incomplete target behavior: forms still treat the synchronous `201` path as the submission result in this phase.

Verify with:

```bash
cd frontend && yarn lint && yarn typecheck && yarn build
```

## Step 5 — Smoke check

1. **Upgrade from the Version 1 head** against representative legacy data:

```bash
cd backend
uv run alembic upgrade head
```

2. **Inspect migrated rows** (via `docker compose exec postgres psql`): legacy `completed` → `succeeded`; legacy `failed` retained; every row has a unique non-null `request_id`; `updated_at` backfilled from `created_at`; all `locked_amount = 0`; `0 <= locked_amount <= amount` holds.
3. **Constraint spot-check** (raw SQL via `psql`): attempt `UPDATE user_wallets SET locked_amount = amount + 1` and confirm the check constraint rejects it; attempt `UPDATE user_wallets SET locked_amount = -1` and confirm rejection.
4. **Index check:** `\d transactions` shows both new indexes; `EXPLAIN` a stale-scan query (`WHERE status = 'submitted' AND created_at < now() - interval '60 seconds'`) and a cursor query (`WHERE (updated_at, id) > (...) ORDER BY updated_at, id LIMIT 100`) and confirm index usage.
5. **Version 1 behavior intact:** log in, run one admin deposit and one exchange through the UI, and confirm read responses carry Version 2 fields with plausible values (mutation routes still use synchronous `201` where the Version 1 path remains active).

## Migration and rollback

- Back up PostgreSQL before applying the migration in any persistent environment and verify a recent isolated restore first.
- Deployment sequence: migrate schema (expand) → deploy code reading the new fields → Phase 3 converts routes one at a time (contract). Old code must never write a status the new constraint rejects, and new code must not run against the pre-migration schema.
- Downgrade is prohibited after Version 2-only statuses or non-zero locks exist unless a reviewed conversion exists; prefer a forward fix when Version 2 data cannot be represented by Version 1.
- Keep worker/reaper code requiring the new schema disabled until the migration revision is verified on the target database.

## Schema compatibility hard stop gate

- [ ] Upgrade from Version 1 completes with no lost transaction history, no duplicate `request_id`, no invalid lock, and no unsupported status.
- [ ] The smoke check exercises migrated data, reservation check constraints, indexes, and cursor-read plans against a real database without anomalies.
- [ ] Rollback / forward-fix policy is written above and approved.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy app` pass from `backend/`; `yarn lint`, `yarn typecheck`, `yarn build` pass from `frontend/`.
