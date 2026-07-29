# Phase 4 — Admin Wallet

**Status:** Intention outline — expand to full step-by-step detail (like [PHASE_2_AUTHENTICATION.md](PHASE_2_AUTHENTICATION.md)) when this phase starts.

Read [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) for architecture rules and [PHASE_3_WALLET_SCHEMA.md](PHASE_3_WALLET_SCHEMA.md) for the wallet tables this phase builds on.

## Purpose

Deliver the **admin operator** wallet experience for Version 1: mock deposits, application-wide transaction history, and admin wallet balances. This is the first phase that adds business logic on top of the Phase 3 schema.

## Prerequisites

- Phase 3 complete: `currencies`, `user_wallets`, `admin_wallets`, and `transactions` tables exist; USD and USDT currencies and admin wallets are seeded.
- Phase 2 authentication unchanged and working.

## Scope

### In scope

- Domain value objects and entities (`Money`, `Asset`, currency/wallet/transaction domain types);
- command and query repository ports plus SQLAlchemy implementations with mappers;
- admin wallet use cases and handlers;
- HTTP admin routes and Pydantic schemas;
- development-only admin React page with `X-Admin-Key` header;
- manual verification and static quality checks.

### Endpoints

| Method | Path | Version 1 behavior |
| --- | --- | --- |
| `GET` | `/reference/currencies` | List all supported currencies, ordered by `label` asc; requires `X-Admin-Key` or Bearer JWT; used by admin deposit currency selector (Phase 4) and user exchange currency selector (Phase 5) |
| `GET` | `/reference/users` | List registered users as `{ user_id, email }`, ordered by `email` asc; requires `X-Admin-Key` or Bearer JWT; used by admin deposit recipient selector (Phase 4) and user transfer recipient selector (Phase 5) |
| `POST` | `/admin/deposits` | Credit target user's wallet for the currency; record `completed` deposit; **does not debit admin** |
| `GET` | `/admin/transactions` | Paginated all-user history (`created_at DESC, id DESC`) |
| `GET` | `/admin/balances` | Admin wallet amounts per currency — likely zero until Phase 5 withdrawals credit admin |

Request/response shapes: [API_CONTRACT.md](../API_CONTRACT.md) § Admin.

### Out of scope

- User wallet routes (`/me/*`) — Phase 5;
- User-to-user `transfer` HTTP API — schema-ready in Phase 3; implement when scoped;
- Kafka / async behavior — Phase 6;
- automated tests — Phase 7.

## Implementation approach

Follow Phase 2's vertical-slice flow. Work feature-by-feature in strict order **Domain → DB → API → UI**. Do not demonstrate a slice until all four layers for that slice are complete.

Suggested slice order:

1a. **Reference currencies** — `GET /reference/currencies`
1b. **Reference users** — `GET /reference/users`
2. **Admin deposit** — `POST /admin/deposits`
3. **Admin balances** — `GET /admin/balances`
4. **Admin transactions** — `GET /admin/transactions`

Within each slice: domain handler and ports first, then repository/mapper methods, then route and schemas, then UI form/list.

### Domain (introduced in this phase)

- `Money`, `Asset` value objects with precision from `currencies.precision` (USD 4, USDT 8; no silent rounding);
- wallet error codes in `domain/error_codes.py` (`INSUFFICIENT_FUNDS`, `ADMIN_ACCESS_DENIED`, validation codes per [API_CONTRACT.md](../API_CONTRACT.md));
- frozen read models for balance lists and transaction pages;
- command handlers: create admin deposit;
- query handlers: list currencies (reference), list users (reference), admin balances, admin all-user transactions;
- separate command vs query repository ports per [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md).

### DB (extends Phase 3)

- mappers: currency, user wallet, admin wallet, transaction ↔ domain;
- command repositories: lock/create user wallets, persist transactions, resolve user by email, resolve currency by label, lock admin wallet on withdrawal path;
- query repositories: list currencies from `currencies`, list users from `users`, project balance list (join `admin_wallets` → `currencies`), and paginated transaction history;
- `SELECT … FOR UPDATE` on user wallets for deposit path (future-proofing for Phase 5 concurrency).

### API

- new router `backend/app/api/routers/admin.py` for admin-key routes;
- new router `backend/app/api/routers/reference.py` for catalog routes (`GET /reference/currencies`, `GET /reference/users`; both with auth dependency accepting admin key or bearer);
- admin key validation dependency (development only; `ADMIN_API_KEY` from settings);
- register router in `main.py`;
- extend `exception_handlers.py` with wallet error codes as handlers return them.

### UI

- development-only Admin page: enter admin key (stored in `sessionStorage`), deposit form (recipient email selected from `GET /reference/users` — show emails only; submit selected **email** to `POST /admin/deposits`, not `user_id`; currency from `GET /reference/currencies`; amount), balances display, transaction list;
- attach `X-Admin-Key` on admin API calls via shared client helper.

## Done when (target)

An operator can open the Admin page in development, enter admin key, load the currency list and user list for the deposit selectors, submit a deposit to a selected user email, see the deposit in admin transaction history, and see admin balances (still zero for currencies not yet received via withdrawal). Invalid admin key returns `403 ADMIN_ACCESS_DENIED`. Backend ruff/mypy and frontend lint/typecheck pass.

## What comes next

[PHASE_5_USER_WALLET.md](PHASE_5_USER_WALLET.md) adds user exchange, withdrawal, balances, and transaction history — completing Version 1 synchronous wallet behavior.
