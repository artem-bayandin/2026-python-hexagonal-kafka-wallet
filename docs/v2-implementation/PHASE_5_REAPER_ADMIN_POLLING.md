# Phase 5 — Stale-submitted reaper and admin long polling

Close the database-to-Kafka publication gap with the stale-`submitted` reaper, and give administrators every transaction update through bounded PostgreSQL long polling on the `(updated_at, id)` cursor.

Work in this order:

1. `reaper-domain-and-db`
2. `reaper-process`
3. `admin-polling-domain-and-db`
4. `admin-polling-api`
5. `admin-polling-ui`
6. `smoke-check`

## Current implementation status

- **Not started** (stale-`submitted` scans, republication, admin long polling). The reaper **process shell** already exists after [PHASE_3A_REFACTORING.md](PHASE_3A_REFACTORING.md): `backend/app/kafka/workers/reaper/main.py`, CLI `uv run python -m app.kafka.workers.reaper`. It runs readiness, starts `build_wallet_publisher`, and idles; `_session_factory` is built and unused until this phase.
- Phase 3 slices **are implemented** (duplicate safety is a prerequisite because reaper republication intentionally permits duplicates). Phase 4 SSE is a separate gate; do not treat this file as implying SSE is already shipped.

Canonical behavior is defined by [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §8/§12/§14, [API_CONTRACT.md](../v2/API_CONTRACT.md) §`GET /admin/transactions`, [CONFIGURATION.md](../v2/CONFIGURATION.md) §7–§8, and [IMPLEMENTATION_STEPS.md](../v2/IMPLEMENTATION_STEPS.md) §Phase 5.

## Purpose

Recover stale `submitted` work safely (never republishing stale `pending` or `in_progress` — those raise alerts for operational investigation), and let administrators observe every insert and status transition through bounded PostgreSQL long polling while the admin UI maintains one current row per transaction.

## Prerequisites

- [ ] The SSE hard stop gate (Phase 4) is green.
- [ ] All four slices have proven duplicate safety.
- [ ] `REAPER_STALE_THRESHOLD_SECONDS` exceeds the producer delivery timeout plus expected commit and scheduler jitter (validated in Phase 1 settings).

## Scope

### In scope

- Reaper: indexed bounded stale scans, concurrency-safe claiming, `WalletTxMessage`/key reconstruction, republication, post-ack guard, failure handling, scheduling, observability.
- Admin long polling: frozen projection, opaque `(updated_at, id)` cursor, keyset query, bounded wait without holding a transaction, `GET /admin/transactions` contract, admin UI polling loop.

### Out of scope

- Repairing stale `pending`/`in_progress` rows (alert only; operational runbook territory).
- Admin SSE or admin reads from Kafka (explicit non-goals).
- Automated tests (deferred).

## Done when

Stale `submitted` work is recovered safely, stale later states are alerted rather than republished, and administrators observe all transaction updates through bounded PostgreSQL long polling with one current row per transaction in the UI.

## Step 1 — Reaper: domain and DB

Create `backend/app/domain/use_cases/recovery/__init__.py` and `backend/app/domain/use_cases/recovery/reap_stale_submitted.py`:

- **Candidate selection:** only `submitted` rows with `created_at < now() - REAPER_STALE_THRESHOLD_SECONDS`.
- **Message reconstruction:** rebuild the exact original `WalletTxMessage` (`request_id`, stored `WalletTxType` as `msg_tx_type`, original `submitted_at`) and the exact original key from authoritative transaction data: the literal `admin` for deposits, the submitting user's UUID string for user commands — resolved from the stored transaction's source/destination wallet ownership, never from a mutable client payload. Publish with `MessagePublisher.publish(*, key, message=...)`.
- **Decisions:** bounded claim → publish → post-ack guarded `submitted → pending` (a zero-row result is a reload-and-observe outcome, never a forced transition) → on publication failure leave the row `submitted` for a later bounded pass → never release a reservation merely because a transaction is old → concurrent reaper instances must not create an avoidable publication storm.

Extend `backend/app/db/repositories/transaction_query_repository.py` (and its port) with:

- `claim_stale_submitted(threshold, batch_size)` — one indexed, bounded scan using `ix_transactions_status_created_at`; claim with `SELECT … FOR UPDATE SKIP LOCKED` (or an equivalent guarded coordination) so multiple reaper instances partition work instead of duplicating it.
- `count_stale_pending(threshold)` / `count_stale_in_progress(threshold)` — alert-only scans; the reaper never selects these rows for republication.

## Step 2 — Reaper: process and operations

Replace the idle loop in `backend/app/kafka/workers/reaper/main.py` (do not recreate `app/kafka/reaper/`). Reuse the existing `wallet_producer` from `build_wallet_publisher` and the unused `session_factory` for scans.

- Every `REAPER_INTERVAL_SECONDS`: run one bounded scan (`REAPER_BATCH_SIZE`, 1–1000), then for each claimed row: reconstruct key and `WalletTxMessage`, publish through `KafkaWalletPublisher` (`acks=all`, idempotence, one `send_and_wait` bounded by `KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS` — no application attempt-count loop), guard `submitted → pending` after acknowledgement.
- A publication failure leaves the row `submitted` and eligible for a later pass; emit an alert-level structured log.
- Publish the same `request_id`, type, original `submitted_at`, and key the API used — never new identities. Worker execute is one attempt per delivery ([PHASE_3A_REFACTORING.md](PHASE_3A_REFACTORING.md)); reaper republish and Kafka redelivery are the retry paths, so duplicate-safe handlers remain mandatory.
- Startup: only after schema revision, `wallet` topic metadata, and the producer are healthy (existing `runtime` readiness). This process does not start a wallet consumer; the command worker is `uv run python -m app.kafka.workers.wallet`.
- Shutdown: stop accepting new scans, let the active bounded scan or publish attempt finish safely, close producer and sessions.
- Observability: structured logs correlated by `request_id`; metrics for scan count, oldest-candidate age, republished count, guarded no-ops, stale `pending`/`in_progress` alerts; one-active-scheduler or leadership evidence (document the chosen mechanism — single local replica plus `SKIP LOCKED` claiming is acceptable for this delivery; record the decision).

Run command (document once verified):

```bash
cd backend && uv run python -m app.kafka.workers.reaper
```

## Step 3 — Admin long polling: domain and DB

Create `backend/app/domain/read_models/admin_cursor.py` — the frozen admin transaction projection (id, request_id, type, status, source_asset, dest_asset, amount, error, created_at, updated_at — no `direction`) and the opaque cursor as the transparent pair `(updated_at, id)`.

Define the semantics next to the read model: ascending keyset order, `limit` 1–100 (default 100), `timeout_seconds` 0–30 (default `ADMIN_LONG_POLL_DEFAULT_SECONDS`), exact timeout response behavior (empty items + input cursor; `null` cursor only for an empty initial result).

Extend `backend/app/db/repositories/transaction_query_repository.py` with:

```sql
SELECT … FROM transactions
WHERE (updated_at, id) > (:updated_at, :id)
ORDER BY updated_at ASC, id ASC
LIMIT :limit
```

- Uses the Phase 2 `ix_transactions_updated_at_id` index; verify with `EXPLAIN`.
- Returns newly inserted rows and later versions of the same row as `updated_at` advances (the same transaction may appear in more than one response).
- The wait mechanism never holds an open transaction or an unbounded connection: reuse the Phase 4 `LISTEN transaction_status_changed` wakeup (or a bounded re-poll interval), re-query PostgreSQL before responding, and loop until rows appear or the timeout elapses. Missed wakeups between the initial query and the wait are impossible because every wakeup triggers a fresh bounded re-query.
- Kafka is entirely outside the admin read path.

## Step 4 — Admin long polling: API

Rework `GET /admin/transactions` in `backend/app/api/routers/admin.py` (replacing the Version 1 offset-paginated variant behind the compatibility boundary):

- Development admin authorization (`X-Admin-Key`) unchanged; production stays prohibited.
- Query params: optional opaque `cursor`; `limit` 1–100 default 100; `timeout_seconds` 0–`ADMIN_LONG_POLL_MAX_SECONDS` default `ADMIN_LONG_POLL_DEFAULT_SECONDS`.
- Cursor codec (create `backend/app/api/cursor_codec.py`): unpadded base64url of the UTF-8 JSON `{"updated_at": "<UTC RFC 3339>", "id": "<canonical UUID>"}`; malformed cursor → `422 VALIDATION_ERROR` without leaking decoder detail.
- No cursor: return the first available page immediately (never waits).
- With a cursor: return available rows immediately, otherwise wait only up to the requested bound.
- Response `{items, next_cursor}`: `next_cursor` encodes the last returned item; on timeout return `{ "items": [], "next_cursor": "<input cursor>" }`; `next_cursor` is `null` only for an empty initial result.
- Cancel waits and release resources promptly on client disconnect.

## Step 5 — Admin long polling: UI

Update `frontend/src/api/adminClient.ts` and `frontend/src/pages/AdminPage.tsx`:

- Start from an initial page (no cursor), process rows in returned order, upsert by transaction `id` (or `request_id`).
- Advance the cursor only after every returned row has been processed.
- Reissue the next request immediately after a response or a healthy timeout; distinguish a healthy timeout (`items: []`, cursor echoed) from an error.
- Retry transient transport failures with bounded backoff.
- Replace an existing row only with a newer `updated_at`; never append duplicate lifecycle versions as separate transactions.
- Stop polling and clear sensitive state when admin authorization is removed or the development-only page is disabled.

## Step 6 — Smoke check

1. **Producer-gap recovery:** stop the API after a `submitted` commit and before publish (or stage a `submitted` row older than the threshold); watch the reaper republish and the command reach exactly one terminal state; inspect the wallet — no double application.
2. **Stale-state discipline:** stage aged `pending` and `in_progress` rows; confirm reaper logs/alerts report them and they are never selected for republication.
3. **Admin long polling:** load the admin page, submit transactions (all four types), and confirm the UI upserts one current row per transaction as statuses advance; confirm `limit`/`timeout_seconds` bounds behave.
4. **Contract edges:** malformed cursor → `422 VALIDATION_ERROR`; timeout with no changes → empty items + input cursor; admin authorization enforced; the admin page remains development-only.

## Migration and rollback

- The Phase 2 stale-scan and cursor indexes are required before enabling the reaper or long polling — verify them on the target database first.
- Stop the reaper before any application rollback, database restore, or repair.
- Do not reset admin cursors server-side during rollback; clients perform bounded resynchronization from PostgreSQL (fresh initial page) when compatibility is lost.
- Coordinate any database restore with stopped API intake, worker, and reaper, plus an explicit Kafka offset and retained-command decision.

## Producer-gap and admin-update hard stop gate

- [ ] Every API crash window exercised in the smoke check is either terminally recorded or recovered by stale-`submitted` republication with no double application.
- [ ] The reaper never touches a non-`submitted` transaction and remains safe with multiple instances.
- [ ] Admin long polling observes creation and every later status version without skipped ordered updates, while the UI maintains one current row per transaction.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app` pass from `backend/`; `yarn lint`, `yarn typecheck`, `yarn build` pass from `frontend/`.

**Done when:** stale `submitted` work is recovered safely, stale later states are alerted rather than republished, and administrators observe all transaction updates through bounded PostgreSQL long polling — completing the Version 2 feature set and unblocking the final operations, documentation, and release gate in [IMPLEMENTATION_STEPS.md](../v2/IMPLEMENTATION_STEPS.md).
