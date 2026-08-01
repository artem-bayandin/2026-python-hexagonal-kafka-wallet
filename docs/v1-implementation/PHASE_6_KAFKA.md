# Phase 6 — Kafka (Version 2)

**Status:** Draft — high-level intentions only. Detailed step-by-step guide to be written when Version 1 (Phases 3–5) is complete.

Read [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) for Version 1 vs Version 2 boundaries. Canonical behavior: [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md) §6, [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md) §9.

## Purpose

Evolve the synchronous wallet into **asynchronous command processing** via Kafka: HTTP submission returns `202 Accepted` with an operation ID; a worker executes deposit, exchange, and withdrawal commands with at-least-once delivery and idempotent processing.

## Prerequisites

- Phases 3–5 complete: Version 1 synchronous wallet working end-to-end.

## Intended scope

### Schema migrations (introduced in this phase, not Phase 3)

- **Balance buckets / pending amounts:** strategy TBD against the Phase 3 `user_wallets` model — e.g. extra columns on `user_wallets`, a child bucket table, or equivalent. Version 2 requires per-currency `pending` and `rejected` balances for users; admin wallets remain a single amount per currency.
- **Transaction statuses:** extend `transactions` to allow `pending`, `rejected`, and additional failure states beyond Version 1 `completed` / `failed`.
- **Outbox messages** table for transactional outbox pattern.
- **Inbox / processed messages** table for duplicate-safe worker consumption.
- **Kafka diagnostics** persistence (or operational columns) for development-only `GET /kafka/messages` queries.

Replace or relax Version 1 check constraints (e.g. `ck_transactions_status_v1`) via reviewed Alembic revisions.

### Infrastructure

- Docker Compose: Kafka broker (pinned image), command worker service.
- `app/messaging/`: Kafka adapter (`aiokafka`), outbox relay, worker dispatch.
- Topic `wallet.commands.v1`, consumer group `wallet-command-worker-v1`, partition key = target user ID.

### Behavior changes

- `POST /admin/deposits`, `POST /me/exchanges`, `POST /me/withdrawals` → `202 Accepted` + operation ID.
- Deposits: mock AML checkbox (`approved` boolean); pending balance increment on accept; worker moves funds pending → available or rejected.
- Exchange/withdraw: no fund reservation at HTTP layer; worker validates current state; may reject if queued prior command spent balance.
- Balance API adds `pending` and `rejected` fields per currency.
- New routes: `GET /me/operations/{id}`, `GET /admin/operations/{id}`.

### Isolated diagnostics module

- `app/kafka_api/`: dev-only router, schemas, read repository — removable without changing wallet domain imports.

### UI (intention)

- Async pending/rejected/failed states with polling (bounded exponential backoff per [CONFIGURATION.md](../CONFIGURATION.md)).
- Development Kafka diagnostics page.
- Admin deposit form gains AML approval checkbox.

## Explicit non-goals (unchanged)

- Real AML, real email, production admin auth replacement.
- Exactly-once end-to-end semantics (at-least-once + idempotency instead).

## Done when (target)

A deposit/exchange/withdraw submission returns `202`, outbox relay publishes to Kafka, worker completes or rejects the operation, wallet amounts and history reflect final state, duplicate messages do not double-apply, and diagnostics are visible in development only.

## What comes next

[PHASE_7_TESTS.md](PHASE_7_TESTS.md) adds automated coverage including Kafka reliability scenarios.
