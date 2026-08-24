# Phase 5A — Admin transaction polling

Give administrators every transaction insert and status transition through PostgreSQL-backed polling on `GET /admin/transactions`, while the admin UI maintains one current row per transaction.

This file is the standalone delivery guide for admin polling. The sibling reaper guide is [PHASE_5B_REAPER.md](PHASE_5B_REAPER.md). The two features are independent.

Work order is **not locked** until the open questions below are decided. A likely sequence after that discussion:

1. `admin-polling-domain-and-db`
2. `admin-polling-api`
3. `admin-polling-ui`
4. `smoke-check`

Canonical HTTP behavior is already defined by [API_CONTRACT.md](../v2/API_CONTRACT.md) §`GET /admin/transactions`, [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §12/§14, [CONFIGURATION.md](../v2/CONFIGURATION.md) §8, and [IMPLEMENTATION_STEPS.md](../v2/IMPLEMENTATION_STEPS.md) §Phase 5 (admin long polling). How that contract is placed in this codebase is **not** decided yet.

---

## Open questions (decide before implementation)

Architecture for this slice is **not locked**. Do not treat the candidate steps later in this file as approved file paths. Resolve these Docs vs Code gaps first.

| # | Docs (original PHASE_5 / v2 contract) | Code (current repo) |
| --- | --- | --- |
| 5 | Create `backend/app/domain/read_models/admin_cursor.py`: frozen admin projection (`id`, `request_id`, `type`, `status`, `source_asset`, `dest_asset`, `amount`, `error`, `created_at`, `updated_at` — no `direction`) and the transparent cursor pair `(updated_at, id)`. | [`TransactionListItem`](../../backend/app/domain/read_models/transaction.py) already has those fields. Admin listing already maps with `viewer_user_id=None`, so `direction` is omitted. `StatusCursor` lives in `notifier/` for user SSE only — admin/domain must not import it. [`AdminTransactionsQuery`](../../backend/app/domain/use_cases/admin/admin_transactions_query.py) / `AdminTransactionsHandler` already exist. |
| 6 | Wait lives with the DB step. Reuse Phase 4 `LISTEN transaction_status_changed` (or a bounded re-poll). Never hold an open transaction. Missed wakeups are recovered by a fresh keyset query after every wakeup. | LISTEN is in [`notifier/adapters/pg_notifier.py`](../../backend/app/notifier/adapters/pg_notifier.py), not in repositories. `pg_notify` fires on `pending` / `in_progress` / `succeeded` / `failed` only — **not** on insert `submitted` ([PHASE_4_SSE_WALLET_UI.md](PHASE_4_SSE_WALLET_UI.md)). Admin routes today are short executor queries (see `get_admin_balances`). Working note from review: **no row locks**; “read once in a period.” Options to pick: periodic short GET vs bounded long-poll wait vs LISTEN wakeup in API. |
| 7 | New [`backend/app/api/cursor_codec.py`](../../backend/app/api/cursor_codec.py): unpadded base64url of `{"updated_at":"<UTC RFC 3339>","id":"<canonical UUID>"}`. Malformed cursor → `422 VALIDATION_ERROR` without leaking decoder detail. | [`SseStatusEncoder`](../../backend/app/api/sse_status_encoder.py) already encodes the same JSON/base64url shape, but **swallows** bad `Last-Event-ID` (`after=None`, no HTTP error) per the SSE contract. Admin `422` and SSE silent-resume are different policies. |
| 8 | Rework `GET /admin/transactions` to `{items, next_cursor}` with `cursor` / `limit` / `timeout_seconds`. Replace the Version 1 offset-paginated variant. | Offset pagination: `page_number`, `page_size`, `total_items`; order `created_at DESC, id DESC` in [`admin.py`](../../backend/app/api/routers/admin.py), `TransactionListResponse`, [`adminClient.ts`](../../frontend/src/api/adminClient.ts), [`AdminPage.tsx`](../../frontend/src/pages/AdminPage.tsx) (“Load more”). `GET /me/transactions` stays offset-paginated either way. |

Hint recorded for that discussion: treat admin as a **standard query** like [`get_admin_balances`](../../backend/app/api/routers/admin.py) — query dataclass + handler + executor + router — unless a later decision says otherwise.

---

## Current implementation status

- **Not started** (no cursor, no long poll, no admin poll loop).
- Phase 3 duplicate-safe execute and Phase 4 user SSE **are implemented**. Admin never uses SSE or Kafka reads ([PHASE_4_SSE_WALLET_UI.md](PHASE_4_SSE_WALLET_UI.md) out of scope still holds).
- Settings exist and are unused by this route: `ADMIN_LONG_POLL_DEFAULT_SECONDS` (25), `ADMIN_LONG_POLL_MAX_SECONDS` (30) on `StreamingSettings` in [`backend/app/config.py`](../../backend/app/config.py).
- Index `ix_transactions_updated_at_id` exists (Phase 2); the admin list query does not use it. The user SSE catch-up query does.
- Sibling reaper work is [PHASE_5B_REAPER.md](PHASE_5B_REAPER.md) and does not block this slice.

## Purpose

Administrators observe creation and every later status version of every transaction through PostgreSQL, and the admin UI shows one current row per transaction.

## Prerequisites

- [ ] The SSE hard stop gate (Phase 4) is green.
- [ ] Open questions in this file are decided and recorded as agreed decisions (same style as Phase 4).

## Scope

### In scope (product)

- `GET /admin/transactions` matching [API_CONTRACT.md](../v2/API_CONTRACT.md): keyset on `(updated_at, id)`, opaque cursor, `limit` / `timeout_seconds` bounds, `{items, next_cursor}`.
- Admin UI that follows the cursor, upserts by `id` / `request_id`, and keeps one current row per transaction.
- Development admin authorization (`X-Admin-Key`); production remains prohibited.

### Out of scope

- Admin SSE or admin reads from Kafka.
- Changing `GET /me/transactions` pagination.
- Reaper scans or republication ([PHASE_5B_REAPER.md](PHASE_5B_REAPER.md)).
- Automated tests (deferred).
- Metrics / Prometheus (deferred, same as Phase 4). Structured logs are allowed.

## Done when

Administrators observe all inserts and status transitions through the agreed PostgreSQL polling contract, the UI maintains one current row per transaction, and the open questions above have been decided and implemented.

## Current code (baseline)

Wiring today matches other admin reads:

| Layer | Path | Behavior |
| --- | --- | --- |
| Router | [`backend/app/api/routers/admin.py`](../../backend/app/api/routers/admin.py) `list_admin_transactions` | `X-Admin-Key`; query `page_number` (default 0), `page_size` (1–100, default 20); `TransactionListResponse` with `total_items`. |
| Executor | [`backend/app/api/executors/admin_transactions.py`](../../backend/app/api/executors/admin_transactions.py) | `read_session` + `build_list_admin_transactions_handler`. Same pattern as [`admin_balances.py`](../../backend/app/api/executors/admin_balances.py). |
| Handler | [`AdminTransactionsHandler`](../../backend/app/domain/use_cases/admin/admin_transactions_query.py) | `get_all_transactions_page`; maps with `viewer_user_id=None`. |
| Repository | [`TransactionQueryRepository.get_all_transactions_page`](../../backend/app/domain/ports/repositories/transaction_query_repository.py) | Offset page, `created_at DESC, id DESC`. |
| UI | [`AdminPage.tsx`](../../frontend/src/pages/AdminPage.tsx) | One-shot load + “Load more”; reconcile by `request_id` only after deposit. No poll loop. |

## Candidate contract (canonical, not an architecture pick)

Until the open questions are answered, implementers should treat this as the **HTTP and UI target** from the v2 contracts, not as a file-path checklist.

### `GET /admin/transactions`

- Query params: optional opaque `cursor`; `limit` 1–100 default 100; `timeout_seconds` 0–`ADMIN_LONG_POLL_MAX_SECONDS` default `ADMIN_LONG_POLL_DEFAULT_SECONDS`. `0` disables waiting.
- Cursor payload: unpadded base64url of UTF-8 JSON `{"updated_at":"<UTC RFC 3339>","id":"<canonical UUID>"}`. Clients treat it as opaque.
- No cursor: return the first available page immediately (never waits).
- With a cursor: return available rows immediately; otherwise wait only up to the requested bound.
- Keyset: `WHERE (updated_at, id) > (:updated_at, :id) ORDER BY updated_at ASC, id ASC LIMIT :limit`. Uses `ix_transactions_updated_at_id`.
- Inserts and every status change bump `updated_at`, so the same transaction may appear in more than one response; clients upsert by `id` or `request_id`.
- Response `{items, next_cursor}`: `next_cursor` encodes the last returned item; on timeout `{ "items": [], "next_cursor": "<input cursor>" }`; `next_cursor` is `null` only for an empty initial result.
- Malformed cursor → `422 VALIDATION_ERROR`.
- Kafka is entirely outside the admin read path.
- Cancel waits and release resources promptly on client disconnect (if a wait exists after question 6).

Item fields match the existing admin projection (no `direction`): `id`, `request_id`, `type`, `status`, `source_asset`, `dest_asset`, `amount`, `error`, `created_at`, `updated_at`.

### Admin UI (candidate)

Update [`frontend/src/api/adminClient.ts`](../../frontend/src/api/adminClient.ts) and [`frontend/src/pages/AdminPage.tsx`](../../frontend/src/pages/AdminPage.tsx):

- Start from an initial page (no cursor), process rows in returned order, upsert by transaction `id` (or `request_id`).
- Advance the cursor only after every returned row has been processed.
- Reissue the next request immediately after a response or a healthy timeout; distinguish a healthy timeout (`items: []`, cursor echoed) from an error.
- Retry transient transport failures with bounded backoff.
- Replace an existing row only with a newer `updated_at`; never append duplicate lifecycle versions as separate transactions.
- Stop polling and clear sensitive state when admin authorization is removed or the development-only page is disabled.

## Candidate steps (blocked on open questions)

Do not implement these file paths until questions 5–8 are decided. They are the original PHASE_5 sketch, kept so the discussion has a concrete alternative.

1. **Domain and DB** — either a new `admin_cursor.py` read model or an extension of `AdminTransactionsQuery` / `TransactionQueryRepository` with the keyset `SELECT`. Wait/LISTEN placement is question 6.
2. **API** — rework `list_admin_transactions` in [`admin.py`](../../backend/app/api/routers/admin.py); cursor encode/decode with `422` on malformed input (question 7). Replace offset params (question 8).
3. **UI** — cursor client and upsert loop as in the candidate UI section.

## Smoke check (after architecture is agreed)

1. Load the admin page, submit transactions (all four types), and confirm the UI upserts one current row per transaction as statuses advance; confirm `limit` / `timeout_seconds` (or the agreed periodic-read equivalent) behave.
2. Malformed cursor → `422 VALIDATION_ERROR` (if an opaque cursor is kept).
3. Timeout or empty poll with no changes → empty items + input cursor (if long poll is kept).
4. Admin authorization enforced; the admin page remains development-only.

## Migration and rollback

- The Phase 2 cursor index `ix_transactions_updated_at_id` is required before enabling keyset polling — verify it on the target database first.
- Do not reset admin cursors server-side during rollback; clients perform bounded resynchronization from PostgreSQL (fresh initial page) when compatibility is lost.

## Admin-update hard stop gate

- [ ] Open questions 5–8 are recorded as agreed decisions in this file.
- [ ] Admin polling observes creation and every later status version without skipped ordered updates, while the UI maintains one current row per transaction.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app` pass from `backend/`; `yarn lint`, `yarn typecheck`, `yarn build` pass from `frontend/`.

**Done when:** administrators observe all transaction updates through the agreed PostgreSQL polling design — completing this half of Version 2 Phase 5. Reaper completion is tracked in [PHASE_5B_REAPER.md](PHASE_5B_REAPER.md). The final operations and release gate remains [IMPLEMENTATION_STEPS.md](../v2/IMPLEMENTATION_STEPS.md).
