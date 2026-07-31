# Phase 5a — Review

Scope: while implementing phases, some questions were left open. In current phase we should review, discuss, possibly improve, and document our findings and decisions regarding the topics listed below.

## Domain/DB

- db.repositories
  - [x] func duplications
  - [x] func names
  - [x] code
  - [x] mappers
  - [x] otp challenge
  - [x] tx query
  - [x] user cmd
  - [x] user q
  - [x] uw cmd
  - [x] uw q
- [x] db.repositories: update docs as func moved and renamed `UserCommandRepositoryImpl.get_by_normalized_email` -> `UserQueryRepositoryImpl.get_by_email` (incl. `AdminDepositHandler`, `TransferHandler`)
- use cases
  - [x] names
  - domain.logic.use_cases
    - admin
      - [x] admin_balances_query
      - [x] admin_deposit_cmd
      - [x] admin_transactions_query
    - auth_session
      - [x] logout_cmd
    - currency
      - [x] currencies_query
    - otp
      - [x] request_otp_cmd
      - [x] verify_otp_cmd
    - user
      - [x] current_user_query
      - [x] user_balances_query
      - [x] user_transactions_query
      - [x] users_query
    - wallet
      - [x] exchange_cmd
      - [x] transfer_cmd
      - [x] withdraw_cmd
- [x] move entities into read_models
- mappers
  - [x] db <-> domain
  - [x] api <-> domain (mapping in routers + `formatting.py`; no separate `api/mappers/` package)

## Repositories

- [x] verify functions names, if these are accurate or not about what's happening inside;
- [x] verify sql commands;
- [x] verify functions to duplicates

## API

- [x] do not use `T = TypeVar("T")`
- Review how executors and handlers are created for routers. It should all go aligned with a single scheme. Executors and Handlers might be the same entity, as well as handling/executing.
- [x] rename `ApiResultError` to `DomainResultError`; rename `unwrap_result` into `unwrap_domain_result` (in `result_mapping.py` and `exception_handlers.py`)

- routers
  - dependencies
    - [x] file itself
    - [x] require_admin_key
    - [x] bind_current_user
      - [x] get_current_user_executor
    - [x] require_admin_or_user_auth (? require_admin_key + bind_current_user ?)
  - admin
    - [x] POST /deposits
      - [x] executor
    - [x] GET /balances
      - [x] executor
    - [x] GET /transactions
      - [x] executor
  - auth
    - [x] POST /otp/request
      - [x] executor
    - [x] POST /otp/verify
      - [x] executor
    - [x] POST /logout
      - [x] executor
  - [x] health
  - reference
    - [x] GET /currencies
      - [x] executor
    - [x] GET /users
      - [x] executor
  - wallet
    - [x] GET /balances
      - [x] executor
    - [x] GET /transactions
      - [x] executor
    - [x] POST /exchanges
      - [x] executor
    - [x] POST /withdrawals
      - [x] executor
    - [x] POST /transfers
      - [x] executor
- schemas
  - [x] admin
  - [x] auth
  - [x] shared (`DataList` in `schemas/shared.py`)
  - [x] errors
  - [x] reference
  - [x] wallet
- [x] current user provider
- [x] exception handlers
- [x] formatting
- [x] result mapping
- [x] dependencies

### Balances/transactions currency lookups

**Why it was split:** Phase 4 reused `CurrenciesQuery` (same handler as `GET /reference/currencies`) so routers could build a `precision_by_label` dict and format `Decimal` amounts to decimal strings in the API layer (`format_asset_amount_wtih_precision`), keeping presentation out of domain handlers.

**Problem:** Each of the four list endpoints ran two executors (two read sessions, two SQL queries) even though balance and transaction repositories already join `currencies` for asset labels.

**Decision:** Project `precision` in the existing balance/transaction repository SELECTs. Read models carry per-row precision (`BalanceItem.precision`; `TransactionListRow` / `TransactionListItem` source/dest precision). Routers use `format_amount_with_precision` with one executor per endpoint. `GET /reference/currencies` is unchanged — it still serves the full catalog via `CurrenciesQuery`.


## Dependencies

**Decision:** Split `backend/app/api/dependencies.py` into auth gates + shared HTTP wiring (kept in `dependencies.py`) and one file per executor under `backend/app/api/executors/` (including `current_user.py` for `get_current_user_executor`, consumed by `bind_current_user`). The module singleton and `get_current_user_provider()` live in `current_user_provider.py`. Routers keep importing executors from `..dependencies` via re-exports (no router changes).

Canonical rules: [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md) §3.4.

**Still open:**

- Rename `backend/app/dependencies.py` (e.g. `handler_builders.py`) to disambiguate from `api/dependencies.py` — larger blast radius.
- `require_admin_or_user_auth` inlines `build_get_current_user_handler` instead of reusing `get_current_user_executor` — optional consistency follow-up.
- Review how executors and handlers are created for routers (executors vs yield-handler injection) — see [LEARN_PY.md](../LEARN_PY.md).

## Other

- [x] require-admin-key + require-jwt = composition of two
- [x] review docs regarding new files structures
- [x] credit_failed

## Typing / PEP stack (Python 3.14)

Baseline: Python 3.14 uses [PEP 695](https://peps.python.org/pep-0695/) for generic syntax (`class Result[T]`, `def foo[T]()`) and [PEP 649](https://peps.python.org/pep-0649/) / [PEP 749](https://peps.python.org/pep-0749/) for deferred annotation evaluation. [PEP 696](https://peps.python.org/pep-0696/) (type-parameter defaults) is optional — adopt only where default type params add clarity. PEP numbers are not a linear version ladder; 695 remains the correct generic syntax on 3.14.

**Verdict:** Application code and canonical docs are aligned for Python 3.14 (PEP 695 generics + PEP 649/749 deferred annotations).

| PEP | Python | Role |
| --- | --- | --- |
| 695 | 3.12+ | Generic syntax — required baseline |
| 696 | 3.13+ | Type-parameter defaults — optional |
| 649 + 749 | 3.14 | Deferred annotations — automatic on 3.14 |

Doc updates applied (2026-07-31 audit):

- [x] Update PHASE_4 pagination snippet: remove `TypeVar` block; keep `class PaginatedResult[T]`
- [x] Add typing policy to TECHNICAL_REQUIREMENTS §2.1

Still open (code, not doc):

- [ ] Fix stale `TypeVar` import in `backend/app/domain/read_models/pagination.py` if still present
- [ ] Review `unwrap_domain_result` cast pattern in `result_mapping.py` — document or simplify if mypy/pyright allow
- [x] Confirm no `from __future__ import annotations` is added (conflicts with 3.14 deferred-eval benefits for runtime introspection)
