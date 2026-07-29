# Phase 5 — User Wallet

**Status:** Intention outline — expand to full step-by-step detail (like [PHASE_2_AUTHENTICATION.md](PHASE_2_AUTHENTICATION.md)) when this phase starts.

Read [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) for architecture rules. Requires Phase 3 schema and Phase 4 admin deposit path (so users can hold balances before exchange/withdraw).

## Purpose

Deliver the **authenticated user** wallet experience for Version 1: view balances, exchange USDT↔USD at 1:1, withdraw to admin custody, transfer to another user (same currency, 1:1), and view personal transaction history. Completes synchronous Version 1 wallet behavior.

## Prerequisites

- Phase 3 schema applied.
- Phase 4 admin deposit working (optional for empty-wallet testing, required for end-to-end demo flows).

## Scope

### In scope

- user wallet command and query handlers;
- repository methods for exchange, withdrawal, and transfer with deterministic wallet locking;
- HTTP user wallet routes and schemas;
- Wallet React page replacing the Phase 2 temporary **Authorized** stub;
- manual verification and static quality checks.

### Endpoints

| Method | Path | Version 1 behavior |
| --- | --- | --- |
| `POST` | `/me/exchanges` | 1:1 exchange; different currencies; exact destination precision; lock both user wallets; `201 Created` |
| `POST` | `/me/withdrawals` | Debit user wallet, credit matching `admin_wallets` row; `201 Created` |
| `POST` | `/me/transfers` | Debit current user wallet, credit recipient wallet (same currency); resolve recipient by **email**; `201 Created` |
| `GET` | `/me/transactions` | User's paginated history (via wallet ownership) |
| `GET` | `/me/balances` | Per-currency amounts (USDT, USD) |

Request/response shapes: [API_CONTRACT.md](../API_CONTRACT.md) § User wallet.

### Out of scope

- Admin routes (Phase 4);
- Kafka / async behavior (Phase 6);
- automated tests (Phase 7).

## Implementation approach

Same vertical-slice flow as Phase 2 and Phase 4: **Domain → DB → API → UI** per feature.

Suggested slice order:

1. **User balances** — `GET /me/balances`
2. **User transactions** — `GET /me/transactions`
3. **Exchange** — `POST /me/exchanges`
4. **Withdrawal** — `POST /me/withdrawals`
5. **Transfer** — `POST /me/transfers`

Queries can precede mutations so the UI has read endpoints before forms.

### Domain

- command handlers: execute exchange, execute withdrawal, execute transfer;
- query handlers: current-user balances, current-user transactions;
- inject `CurrentUserProvider` — no `current_user` on command DTOs;
- enforce: positive amounts, supported currencies, distinct exchange currencies, sufficient funds, exact destination precision, 1:1 rate.

### DB

- extend command repositories: lock user and admin wallets in deterministic order (by wallet `id`);
- atomic debit/credit + single `completed` transaction row per mutation;
- query repositories: user-scoped wallet and transaction projections (join `user_wallets` → `currencies` for labels).

### API

- new router `backend/app/api/routers/wallet.py` (or split per convention);
- routes use `Depends(bind_current_user)`;
- map read models to response DTOs; commands via executors in `dependencies.py`.

### UI

- Wallet page: balance list, exchange form (currencies from `GET /reference/currencies`), withdrawal form, transfer form (recipient selector from `GET /reference/users` — show emails only; submit selected **email**, not `user_id`), link or section for history;
- History page or embedded list with cursor pagination;
- replace minimal **Authorized** state from Phase 2 with navigation to Wallet;
- keep login/logout flow unchanged.

## Business rules (reminder)

From [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md) §5:

- Exchange rate fixed at 1 USDT = 1 USD.
- Transfer is same-currency, 1:1; recipient resolved by email.
- Withdrawal credits the matching `admin_wallets` row — after this phase, admin balances become non-zero.
- One immutable business transaction per deposit, exchange, withdrawal, or transfer.
- Insufficient funds → `409 INSUFFICIENT_FUNDS`.

## Done when (target)

A logged-in user can view balances, exchange between USDT and USD, withdraw to admin, transfer to another user by email, and page through their history. Admin balances reflect withdrawals. Concurrent exchange/withdraw/transfer attempts cannot drive wallet amounts negative (verified manually until Phase 7). Backend ruff/mypy and frontend lint/typecheck pass.

## What comes next

[PHASE_6_KAFKA.md](PHASE_6_KAFKA.md) evolves wallet mutations to asynchronous Kafka processing (Version 2).
