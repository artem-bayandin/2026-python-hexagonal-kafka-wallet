# Readme — Version 2: Kafka

## References

- [Version 1 docs](../v1/README.md) keeps a list of docs regarding the current version 1.
- [PHASE_2A_INSIGHTS.md](../v1-implementation/PHASE_2A_INSIGHTS.md) keeps notes regarding what was changed in docs whithin implementation of Version 1.

## Reading order

| Document | Authority | Purpose |
| --- | --- | --- |
| [Functional requirements](FUNCTIONAL_REQUIREMENTS.md) | Canonical product contract | Defines user-visible behavior, the asynchronous wallet lifecycle, and non-goals. |
| [Technical requirements](TECHNICAL_REQUIREMENTS.md) | Canonical architecture contract | Defines stack, boundaries, messaging, persistence, reliability, security, and verification rules. |
| [API contract](API_CONTRACT.md) | Canonical HTTP and SSE contract | Defines payloads, HTTP outcomes, SSE events, cursor semantics, errors, and compatibility. |
| [Configuration](CONFIGURATION.md) | Canonical configuration contract | Defines profiles, environment variables, Kafka and process settings, ports, and secret policy. |
| [Operations](OPERATIONS.md) | Canonical operating contract | Defines health checks, lifecycle commands, observability, runbooks, backup, release, and rollback expectations. |
| [Implementation steps](IMPLEMENTATION_STEPS.md) | Canonical delivery plan | Defines the build sequence, slice gates, and completion criteria. |
| [Phase guides](../v2-implementation/) | Runnable delivery guides | Step-by-step guides for each implementation phase, added as phases are executed. |

This README defines the agreed architecture decisions and the change rules below; change behavior only in the canonical document for that concern, and record intentionally incompatible API or data changes before implementing them.

## Purpose

Switch all four wallet operations — **admin deposit, user withdrawal, user exchange, user transfer** — from synchronous HTTP execution to **asynchronous processing via Kafka**. Submission returns `202 Accepted` + `request_id`; a command worker executes the operation; the user watches a live status lifecycle (`submitted → pending → in_progress → succeeded|failed`) over a server-to-client stream; balances refresh on success. Admin observes everything via long polling.

## Requirements and constraints (from the initial task)

| # | Requirement | Design consequence |
| --- | --- | --- |
| 1 | All transactions of a specific user must arrive into one concrete Kafka partition | partition key = `user_id` |
| 2 | All admin transactions (deposit) must arrive into a single admin partition | partition key = fixed literal `"admin"` |
| 3 | Every transaction processed at least once AND idempotently (redelivery must not double assets) | unique `request_id`, guarded status transitions, worker re-derives state from DB |
| 4 | Real-time transaction statuses for users | SSE channel (chosen over WebSocket / long polling) |
| 4a | Admin prefers long polling | admin reads Postgres only — no Kafka in the admin path |
| 5 | [optional] Lock debit amounts early so "already to be spent" value can't be spent twice | chosen: lock at submit via `wallets.locked_amount` |

## Decisions log (agreed 2026-08-03)

| Topic | Decision | Rejected alternatives |
| --- | --- | --- |
| Submit → Kafka | Direct publish after DB commit + reaper for stuck `submitted` | transactional outbox table; Debezium CDC |
| User real-time channel | SSE (`GET /me/stream`) — one-way, auto-reconnect | WebSocket; long polling |
| Admin updates | Long polling with `(updated_at, id)` keyset cursor, DB only | SSE/WS for admin; `since=<id>` alone |
| Locking | Lock at submit, settle/release in worker | lock at `in_progress`; no lock |
| Topic layout | Single topic `wallet`, key = `user_id` / `"admin"` | topic per action |
| Worker failure handling | Retry 3× with backoff → `failed` + release lock + Dead Letter Queue (DLQ) | fail-fast; infinite retry (blocks partition) |

Upgrade path: switching to a transactional outbox later is a **submit-side-only change** — worker, topics, SSE, and admin polling are untouched. The reaper (`submitted` + age → republish) already provides most of the outbox benefit without new tables.

## Architecture

```text
UI (React)                API (hexagonal, sync submit)             Kafka                Command worker
─────────────────         ──────────────────────────────           ─────────────────   ─────────────────────────
POST /me/withdrawals ──►  validate + LOCK (locked_amount)          'wallet' topic ──►  guard pending
                          INSERT tx(submitted); COMMIT             key=user_id          → in_progress
                          producer.send (acks=all)                 key="admin"          → domain logic (Phase 3–5)
◄── 202 {request_id}      → UPDATE status=pending                  N partitions         → retry 3× backoff
                                                                                        → succeeded | failed + DLQ
SSE GET /me/stream   ◄──  status-change events (DB = source of truth)
on succeeded → refetch balances; on failed → show error
Admin UI: long-poll GET /admin/transactions (updated_at, id cursor)   (DB only, no Kafka)
```

Components: existing API gains a Kafka producer; new **command worker** process reuses Phase 3–5 domain services and repositories; new **SSE notifier** inside the API process; new **reaper** periodic task.

## Transaction lifecycle

| Status | Set by | Meaning |
| --- | --- | --- |
| `submitted` | API (INSERT, same DB tx as the lock) | created + funds locked; publish not yet acked |
| `pending` | API (guarded UPDATE after producer ack) | in Kafka, awaiting worker |
| `in_progress` | worker (guarded UPDATE) | executing; retries keep this status |
| `succeeded` | worker | terminal; lock settled |
| `failed` | API on publish failure; worker after final retry | terminal; lock released; `error` column set |

Guards (all transitions idempotent):

- pending: `UPDATE ... SET status='pending' WHERE id=? AND status='submitted'`
- in_progress: `UPDATE ... SET status='in_progress' WHERE id=? AND status='pending'`
- terminal: `UPDATE ... WHERE id=? AND status='in_progress'`

Consequences:

- UI must tolerate skipped states — a fast tx may jump `submitted → succeeded` shortly.
- Reaper semantics: `submitted` older than threshold ⇒ publish was lost ⇒ **republish**. `pending` + old ⇒ message is already in Kafka; consumer is down or lagging ⇒ **alert, never republish**. Stuck `in_progress` after worker death ⇒ **alert / manual**, never republish (same spirit as stale `pending`). Exhausted worker retries ⇒ terminal `failed` + DLQ, not reaper territory.
- Kafka down at submit: producer retries exhausted ⇒ tx → `failed` immediately ("submit failed"), lock released. No hanging transactions.

## Kafka layout

- Topic `wallet` (dev default 3 partitions). Key = `user_id` (string) for user operations → per-user ordering and even spread. Key = literal `"admin"` for deposits → single admin partition by design (low volume, ordering preserved).
- Topic `wallet_dlq` — Dead Letter Queue for poison messages after final retry, with error context for replay. After 3 in-process failures the worker marks the tx `failed`, publishes to `wallet_dlq`, and acks the original `wallet` message so the partition does not block. No DLQ table in Postgres unless a replay UI is wanted later.
- Consumer group `wallet_worker`; dispatch by message `type` field (`deposit|withdrawal|exchange|transfer`).
- Message envelope: `{request_id, type, submitted_at}` — the worker loads the transaction row from Postgres (DB is truth); payload in the message is for diagnostics only.
- Producer: `acks=all`, `enable.idempotence=true`, bounded retries.

## Idempotency (at-least-once without double-spend)

Kafka exactly-once does not cover Postgres writes — DB guards are the real mechanism:

1. `request_id` UUID generated at submit, unique on `transactions`.
2. Guarded status transitions (above): a redelivered message matches 0 rows → ack and skip.
3. All wallet mutations of one command execute in a single DB transaction in the worker, keyed by the transaction row — replays converge to the same final state.

## Locking (debit side: withdrawal, exchange, transfer)

- Submit (same DB transaction as the INSERT): `UPDATE user_wallets SET locked_amount = locked_amount + :amt WHERE user_id=? AND currency_id=? AND amount - locked_amount >= :amt` — 0 rows ⇒ `409 INSUFFICIENT_FUNDS` synchronously, nothing is created.
- `GET /me/balances` returns `amount` (total) and `locked` (`locked_amount`) per currency; the UI computes spendable as `amount - locked` if needed.
- Settle on success: `amount -= amt; locked_amount -= amt`, plus credit the counterparty (admin wallet for withdrawal, destination wallet for exchange, recipient for transfer) — all in the worker's single DB transaction.
- Release on failure: `locked_amount -= amt`.
- Deposit never locks (credit-only).

## SSE and UI

- `GET /me/stream` (SSE): emits `{request_id, status, error?}` on every transition of the authenticated user's transactions. At sample scale the DB stays the source of truth; the notifier uses an in-process event bus, a 1s poll, or Postgres `LISTEN/NOTIFY` — pick at implementation time. Swappable for a `transaction-status-changed` topic if the notifier ever scales out.
- User UI: transaction list shows a status stepper that tolerates skipped states; on `succeeded` refetch balances; on `failed` display `error`.
- Admin UI: long-poll `GET /admin/transactions` with a keyset cursor on `(updated_at, id)` — not `since=<last_seen_id>` alone (`id` is a UUID and is not monotonic). Query shape: `WHERE (updated_at, id) > (:since_updated_at, :since_id) ORDER BY updated_at ASC, id ASC` (or one opaque cursor encoding both). New submits set `updated_at` at insert; later status changes bump `updated_at`, so the same row can appear again — admin UI upserts by `id` / `request_id`. Long processing cannot be skipped: the row is visible from create, and each transition is another cursor event.

## Schema migrations (Alembic)

- `transactions`: status set extended to `submitted|pending|in_progress|succeeded|failed` (replace/relax `ck_transactions_status_v1`; map legacy `completed → succeeded` (rename)); add `request_id UUID UNIQUE NOT NULL`, `error TEXT NULL`, `updated_at TIMESTAMPTZ`. No `attempts` column — worker retries are in-process only (see below).
- `user_wallets`: `locked_amount NUMERIC NOT NULL DEFAULT 0` with checks `locked_amount >= 0` and `amount - locked_amount >= 0`.
- DLQ is a Kafka topic — no table (unless a DLQ replay UI is wanted later).

## Worker retries

Retries are a **local loop** in the command worker for one Kafka delivery (`max_attempts=3`), not a persisted field on `transactions`:

```text
consume message
  → load tx; if terminal → ack+skip (idempotent)
  → guard → in_progress
  → for attempt in 1..3:
        try domain work in one DB tx → succeeded; ack; return
        on retryable error → backoff; stay in_progress
  → after 3 failures → failed + release lock + write error + publish DLQ + ack
```

Terminal `failed` + `error` is the persisted outcome. Status stays `in_progress` during the retry loop. Redelivery after a crash mid-loop: Kafka delivers again; DB guards prevent double-spend; the worker may run another up-to-3 cycle if still non-terminal. Infinite crash loops are an ops concern (lag/alerts), not a V2 schema field. Add a DB `attempts` column later only if a crash-budget across redeliveries is required.

## API changes

| Method | Path | Change |
| --- | --- | --- |
| `POST` | `/admin/deposits` | → `202` + `{request_id}`; key `"admin"`; no lock |
| `POST` | `/me/withdrawals` | → `202` + `{request_id}`; lock at submit |
| `POST` | `/me/exchanges` | → `202` + `{request_id}`; lock source wallet at submit |
| `POST` | `/me/transfers` | → `202` + `{request_id}`; lock source wallet at submit; recipient resolved at submit, re-validated by worker |
| `GET` | `/me/stream` | new SSE endpoint |
| `GET` | `/me/transactions` | include `status`, `request_id`, `error` |
| `GET` | `/me/balances` | include `amount` and `locked` (UI computes spendable) |
| `GET` | `/admin/transactions` | add `(updated_at, id)` keyset cursor for long polling; include statuses |

## Implementation phases

Strict Domain → DB → API → UI within each slice (where a slice spans those layers).

1. **kafka-infra** — single slice: Docker Compose Kafka broker (pinned image), topic bootstrap (`wallet`, `wallet_dlq`), configuration settings, `app/kafka/messaging/` producer adapter (`aiokafka`).
2. **async-schema** — single slice: Alembic migration (statuses, `request_id`, `error`, `updated_at`, `locked_amount`); domain status enum and guarded transition helpers.
3. **async-submit-worker** — vertical per transaction type. Optional **Slice 0**: shared submit/worker skeleton (producer wiring, consumer process, dispatcher stub, lock helpers, message envelope). Then **Slice 1–4** in order **deposit → withdrawal → exchange → transfer**: each slice takes that type end-to-end through async submit (`202` + lock/publish where applicable) and the command-worker path (consume, guarded transitions, domain settle/release, retry 3× → `failed` + DLQ), reusing Phase 3–5 repositories and domain services.
4. **user-live-status** — SSE route + notifier; UI status stepper, balance refetch on success, error display.
5. **reaper-and-admin-polling** — reaper task (stuck `submitted` → republish), `(updated_at, id)` cursor on admin transactions, admin UI polling update (upsert by `id` / `request_id`).

## Explicit non-goals

- Transactional outbox table / Debezium CDC (upgrade path documented above; the reaper suffices at this scale).
- WebSocket transport; multiple events per transaction; a separate status topic (until notifier scale-out).
- Exactly-once end-to-end semantics (at-least-once + DB idempotency instead).
- Real AML, real email, production admin auth replacement (unchanged from Version 1).
- Persisted worker `attempts` column (in-process retry loop only at this scale).

## Done when

All four operations return `202` + `request_id`; statuses advance `submitted → pending → in_progress → succeeded|failed` visibly in the user UI via SSE; balances refresh on success; locked amounts settle/release correctly; duplicate delivery never double-applies (verified by killing the worker mid-process and forcing redelivery); admin sees all transactions with live statuses via long polling on `(updated_at, id)`; poison messages land in the DLQ; the reaper republishes a stuck `submitted` transaction; backend ruff/mypy and frontend lint/typecheck pass.

## What comes next

To be discussed.
