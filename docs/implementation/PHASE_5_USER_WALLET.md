# Phase 5 — User Wallet

Implement authenticated user wallet features end to end in five vertical feature slices, in this exact order:

1. `user-balances`
2. `user-transactions`
3. `exchange`
4. `withdrawal`
5. `transfer`
6. `ui-polish` (transaction list enrichment, wallet/admin layout, integration fixes — see Slice 6)

Within each feature slice, work in the strict order **Domain → DB → API → UI**. Do not run or demonstrate a feature slice until all four sections in that slice are complete.

Read [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) for architecture rules, [PHASE_3_WALLET_SCHEMA.md](PHASE_3_WALLET_SCHEMA.md) for wallet tables and transaction semantics, and [PHASE_4_ADMIN_WALLET.md](PHASE_4_ADMIN_WALLET.md) for entities, reference routes, shared schemas, and the admin deposit path this phase depends on.

## Current implementation status

- **Phase 3 wallet schema** complete (migration `d377d8c90992`).
- **Phase 4 admin wallet** complete (reference routes, deposit, admin balances, admin transactions).
- **Slice 1** complete (`GET /me/balances`, `WalletPage` balances, `walletClient`, `authenticatedFetch` export).
- **Slice 2** complete (`GET /me/transactions`, user ownership filter, history table with Load more).
- **Slice 3** complete (`POST /me/exchanges`, exchange form, `INSUFFICIENT_FUNDS` → 409).
- **Slice 4** complete (`POST /me/withdrawals`, `AdminWalletCommandRepository`, withdrawal form).
- **Slice 5** complete (`POST /me/transfers`, transfer form, reference users/currencies via Bearer JWT).
- **Slice 6** complete (transaction list `asset` / `amount`, wallet and admin wide layout, reference-auth and email-normalization fixes).
- **Final verification** not started.

Implementation note: `GET /me/transactions` uses offset pagination (`page_number`, `page_size`, `total_items`) matching Phase 4 admin history and the existing `TransactionListResponse` shape, rather than the cursor shape described in [API_CONTRACT.md](../API_CONTRACT.md). The running code is canonical; align the contract in a follow-up if needed.

Canonical behavior is defined by [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md), [API_CONTRACT.md](../API_CONTRACT.md), [CONFIGURATION.md](../CONFIGURATION.md), and [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md). Those documents and this guide are aligned on the phase-specific scope below.

## Purpose

Deliver the **authenticated user** wallet experience for Version 1: view balances, exchange USDT↔USD at 1:1, withdraw to admin custody, transfer to another user (same currency, 1:1), and view personal transaction history. Completes synchronous Version 1 wallet behavior.

## Prerequisites

- Phase 3 complete: `currencies`, `user_wallets`, `admin_wallets`, and `transactions` tables exist; USD and USDT currencies and admin wallets are seeded.
- Phase 4 complete: admin deposit works so a user can hold balances before exchange/withdraw/transfer; `GET /reference/currencies` and `GET /reference/users` accept Bearer JWT; shared `Money` / `Asset` / wallet entities and `api/schemas/wallet.py` exist.
- Phase 2 authentication unchanged and working (`bind_current_user`, JWT in `sessionStorage`).

## Scope

### In scope

- user wallet command and query handlers;
- repository methods for exchange, withdrawal, and transfer with deterministic wallet locking;
- HTTP user wallet routes and schemas under `/me/*`;
- Wallet React page replacing the Phase 2 temporary **Authorized** stub;
- manual verification and static quality checks.

### Endpoints

| Method | Path | Version 1 behavior |
| --- | --- | --- |
| `GET` | `/me/balances` | Per-currency amounts (USDT, USD) for the current user; missing wallet → `"0"` at currency precision |
| `GET` | `/me/transactions` | User's paginated history via wallet ownership; query params `page_number` (default 0), `page_size` (1–100, default 20); response includes `total_items` |
| `POST` | `/me/exchanges` | 1:1 exchange; different currencies; exact destination precision; lock both user wallets; `201 Created` |
| `POST` | `/me/withdrawals` | Debit user wallet, credit matching `admin_wallets` row; `201 Created` |
| `POST` | `/me/transfers` | Debit current user wallet, credit recipient wallet (same currency); resolve recipient by **email**; `201 Created` |

Request/response shapes: [API_CONTRACT.md](../API_CONTRACT.md) § User wallet (except transaction pagination — offset as noted above).

Reuse without re-implementing:

| Method | Path | Role in Phase 5 |
| --- | --- | --- |
| `GET` | `/reference/currencies` | Exchange / withdrawal asset selectors (Bearer JWT) |
| `GET` | `/reference/users` | Transfer recipient selector — show emails; submit email (Bearer JWT) |

### Out of scope

- Admin routes and Admin UI changes (Phase 4) — except observing that withdrawals credit admin balances;
- Kafka / async behavior (Phase 6);
- automated tests (Phase 7);
- Version 2 fields (`pending` / `rejected` balances, operations API).

## Done when

A logged-in user can view balances, exchange between USDT and USD, withdraw to admin, transfer to another user by email, and page through their history. Admin balances reflect withdrawals. Concurrent exchange/withdraw/transfer attempts cannot drive wallet amounts negative (verified manually until Phase 7). Backend ruff/mypy and frontend lint/typecheck pass.

## Architecture rules

Follow [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) § Architectural invariants. Phase 5 adds:

- `/me/*` wallet routes require Bearer JWT via existing `Depends(bind_current_user)`; no `X-Admin-Key` on these routes;
- inject `CurrentUserProvider` into handlers — no `current_user` / `user_id` on command or query DTOs;
- reuse Phase 4 domain types (`Money`, `Asset`, `Currency`, `UserWallet`, `Transaction`, `BalanceItem`, `TransactionListItem`, `PaginationParams`);
- wallet mutations use one `AsyncSession.begin()` per command; query routes use short-lived read sessions without an explicit write transaction;
- lock all affected wallets with `SELECT … FOR UPDATE` in deterministic order before debit/credit;
- `Money` precision comes from the `currencies` catalog; no silent rounding; exchange destination amount must be exactly representable at destination precision;
- user transaction history uses offset pagination (`page_number`, `page_size`, `total_items`), matching Phase 4 admin history.

## Shared implementation notes

This section is reference material, not an implementation stage. It contains no create/update step. Complete file contents appear in Slice 1–6 at the point they are created or updated, preserving the Domain → DB → API → UI order.

### Target layout

Use this final target layout as a reference only. Phase 3 ORM models and Phase 4 domain/API pieces already exist; Phase 5 extends them and adds the user wallet surface.

```text
backend/
└── app/
    ├── dependencies.py              # extend with user-wallet handler builders
    ├── main.py                      # register wallet router
    ├── api/
    │   ├── dependencies.py          # bind_current_user; user-wallet executors; require_admin_or_user_auth fix (Slice 6)
    │   ├── formatting.py            # reuse format_asset_amount_wtih_precision
    │   ├── exception_handlers.py    # map INSUFFICIENT_FUNDS → 409 (Slice 3)
    │   ├── routers/
    │   │   └── wallet.py            # new — /me/* routes
    │   └── schemas/
    │       └── wallet.py            # reuse Balance*/Transaction*; add mutation request DTOs
    ├── db/
    │   └── repositories/
    │       ├── user_wallet_query_repository.py      # new (Slice 1)
    │       ├── user_wallet_command_repository.py    # extend: debit, lock ordered (Slice 3)
    │       ├── admin_wallet_command_repository.py   # new (Slice 4)
        │       └── transaction_query_repository.py      # extend: get_user_transactions_page (Slice 2); currency joins (Slice 6)
    └── domain/
        ├── ports/repositories/
        │   ├── user_wallet_query_repository.py      # new
        │   ├── user_wallet_command_repository.py    # extend
        │   ├── admin_wallet_command_repository.py   # new
        │   └── transaction_query_repository.py      # extend
        └── use_cases/
            └── wallet/
                ├── user_balances_query.py
                ├── list_user_transactions_query.py
                ├── exchange_cmd.py
                ├── withdraw_cmd.py
                └── transfer_cmd.py

frontend/src/
├── types/wallet.ts
├── utils/email.ts                   # normalizeEmail (Slice 6)
├── utils/transaction.ts             # formatTransactionAsset (Slice 6)
├── api/client.ts                    # export authenticatedFetch; store user_email on verify
├── api/walletClient.ts
├── App.css                          # wallet-page layout (Slice 6)
└── pages/
    ├── WalletPage.tsx               # replaces Authorized stub
    └── AdminPage.tsx                # wide layout aligned with wallet (Slice 6)
```

### Cross-cutting rules

- **Command vs query ports:** command repositories lock and mutate; query repositories project read models only. Concrete classes use the `*Impl` suffix and live under `app/db/repositories/`.
- **User auth:** `/me/*` succeeds only with a valid Bearer JWT (`bind_current_user`). Missing/invalid token → `401 AUTHENTICATION_FAILED`.
- **Identity:** handlers call `current_user_provider.get()` for the acting user; command DTOs carry only request fields (assets, amounts, recipient email).
- **Transaction row shapes** (from Phase 3):

| Operation | source_wallet_id | dest_wallet_id | amounts | wallet updates |
| --- | --- | --- | --- | --- |
| **Exchange** | user A wallet (curr X) | user A wallet (curr Y) — create if missing | `source = dest` (1:1) | debit X; credit Y |
| **Withdrawal** | user wallet | `NULL` (admin/system) | `source = dest` | debit user; credit `admin_wallets` for that currency |
| **Transfer** | user A wallet (curr X) | user B wallet (curr X) — create if missing | `source = dest` (1:1) | debit A; credit B |

- **Concurrency — user wallets:** when two or more `user_wallets` rows are involved (exchange, transfer), ensure both exist, then `SELECT … FOR UPDATE` with `ORDER BY id` ascending so concurrent opposite operations cannot deadlock.
- **Concurrency — withdrawal:** lock the user wallet with `FOR UPDATE`, then lock the matching `admin_wallets` row (`currency_id` PK) with `FOR UPDATE`. Admin wallets have no separate wallet `id`; fixed order user-then-admin is the Version 1 rule.
- **Debit:** atomic `UPDATE … SET amount = amount - :amt WHERE id = :id AND amount >= :amt`; if no row updated → `409 INSUFFICIENT_FUNDS`.
- **Offset pagination (user transactions):** same rules as admin — `page_number` (≥ 0, default 0), `page_size` (1–100, default 20), `ORDER BY created_at DESC, id DESC`, response includes `total_items`.
- **User history filter** (Phase 3 CTE pattern — one row per transaction, no join duplicates):

```sql
WITH user_wallet_ids AS (
  SELECT id FROM user_wallets WHERE user_id = :uid
)
SELECT t.*
FROM transactions t
WHERE t.source_wallet_id IN (SELECT id FROM user_wallet_ids)
   OR t.dest_wallet_id IN (SELECT id FROM user_wallet_ids)
ORDER BY t.created_at DESC, t.id DESC;
```

- **Reference reuse:** exchange/transfer UI loads currencies and users from Phase 4 `GET /reference/*` with the user's Bearer token (already accepted by `require_admin_or_user_auth`).
- **Shared response DTOs:** reuse `BalanceItemResponse`, `BalanceListResponse`, `TransactionItemResponse`, `TransactionListResponse` from `api/schemas/wallet.py` and `format_asset_amount_wtih_precision` from `api/formatting.py`. From Slice 6 onward, `TransactionItemResponse` includes `source_asset`, `dest_asset`, and formatted `amount` (see Slice 6).

### Error codes introduced incrementally

| Code | HTTP | Introduced in |
| --- | --- | --- |
| `INSUFFICIENT_FUNDS` | 409 | Slice 3 (domain constant already exists from Phase 4; map in `exception_handlers.py` here) |

Reuse Phase 4 mappings unchanged:

| Code | HTTP | Already mapped |
| --- | --- | --- |
| `USER_NOT_FOUND` | 404 | Phase 4 |
| `UNSUPPORTED_ASSET` | 422 | Phase 4 |
| `INVALID_AMOUNT` | 422 | Phase 4 |
| `INVALID_PRECISION` | 422 | Phase 4 |
| `AUTHENTICATION_FAILED` | 401 | Phase 2 |

Request-shape validation remains Pydantic `422 VALIDATION_ERROR`. Self-transfer (recipient email is the current user) returns `422 INVALID_AMOUNT` in Version 1 (no dedicated self-transfer code).

## Slice 1 — user balances

### Domain

Create `backend/app/domain/ports/repositories/user_wallet_query_repository.py`:

```python
from typing import Protocol
from uuid import UUID

from ...read_models.balance_item import BalanceItem


class UserWalletQueryRepository(Protocol):
    async def get_user_balances(self, user_id: UUID) -> list[BalanceItem]: ...
```

Return one `BalanceItem` per catalog currency (ordered by `label` asc). If the user has no `user_wallets` row for a currency, `available` is `Decimal("0")`.

Create `backend/app/domain/use_cases/user/user_balances_query.py`:

```python
from dataclasses import dataclass

from ...ports import CurrentUserProvider
from ...ports.repositories.user_wallet_query_repository import UserWalletQueryRepository
from ...read_models.balance_item import BalanceItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class UserBalancesQuery:
    pass


class UserBalancesHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        user_wallet_query_repo: UserWalletQueryRepository,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._user_wallet_query_repo = user_wallet_query_repo

    async def handle(self, _: UserBalancesQuery) -> Result[list[BalanceItem]]:
        user = self._current_user_provider.get()
        items = await self._user_wallet_query_repo.get_user_balances(user.id)
        return Result.success(items)
```

Create `backend/app/domain/use_cases/wallet/__init__.py` re-exporting the query symbols used by façades.

#### Package façade update

Export `UserWalletQueryRepository`, `UserBalancesHandler`, and `UserBalancesQuery` from `domain/ports/__init__.py` / `domain/use_cases/__init__.py` / `domain/__init__.py` as appropriate (match Phase 4 façade style).

### DB

Create `backend/app/db/repositories/user_wallet_query_repository.py`:

```python
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.domain import BalanceItem, UserWalletQueryRepository

from ..models import CurrencyModel, UserWalletModel
from ..session import AsyncSession


class UserWalletQueryRepositoryImpl(UserWalletQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_balances(self, user_id: UUID) -> list[BalanceItem]:
        stmt = (
            select(CurrencyModel.label, UserWalletModel.amount)
            .select_from(CurrencyModel)
            .outerjoin(
                UserWalletModel,
                (UserWalletModel.currency_id == CurrencyModel.id)
                & (UserWalletModel.user_id == user_id),
            )
            .order_by(CurrencyModel.label.asc())
        )
        result = await self.session.execute(stmt)
        return [
            BalanceItem(
                asset=row.label,
                available=row.amount if row.amount is not None else Decimal("0"),
            )
            for row in result.all()
        ]
```

In `backend/app/dependencies.py`, add:

```python
def build_get_user_balances_handler(
    session: AsyncSession,
    current_user_provider: CurrentUserProvider,
) -> UserBalancesHandler:
    return UserBalancesHandler(
        current_user_provider,
        UserWalletQueryRepositoryImpl(session),
    )
```

#### Package façade update

Export `UserWalletQueryRepositoryImpl` from `db/repositories/__init__.py` / `db/__init__.py` if other Impls are re-exported there.

### API

Create `backend/app/api/routers/wallet.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from app.domain import UserBalancesQuery, CurrenciesQuery

from ..dependencies import (
    GetUserBalancesExecutor,
    ListCurrenciesExecutor,
    bind_current_user,
    get_get_user_balances_executor,
    get_list_currencies_executor,
)
from ..formatting import format_asset_amount_wtih_precision
from ..result_mapping import unwrap_result
from ..schemas.wallet import BalanceItemResponse, BalanceListResponse

router = APIRouter(prefix="/me", tags=["wallet"])


@router.get(
    "/balances",
    dependencies=[Depends(bind_current_user)],
)
async def get_user_balances(
    balances_executor: Annotated[
        GetUserBalancesExecutor, Depends(get_get_user_balances_executor)
    ],
    currencies_executor: Annotated[
        ListCurrenciesExecutor, Depends(get_list_currencies_executor)
    ],
) -> BalanceListResponse:
    items = unwrap_result(await balances_executor(UserBalancesQuery()))
    currencies = unwrap_result(await currencies_executor(CurrenciesQuery()))
    precision_by_label = {item.label: item.precision for item in currencies}
    return BalanceListResponse(
        items=[
            BalanceItemResponse(
                asset=item.asset,
                available=format_asset_amount_wtih_precision(
                    item.available, item.asset, precision_by_label
                ),
            )
            for item in items
        ]
    )
```

Wire `GetUserBalancesExecutor` and `get_get_user_balances_executor` in `api/dependencies.py`: open a short-lived read session, bind `get_current_user_provider()`, call `build_get_user_balances_handler`, invoke the handler. Mirror the Phase 2 logout executor pattern for provider injection.

Register the router in `main.py`:

```python
from app.api import wallet_router  # or from app.api.routers.wallet import router

app.include_router(wallet_router)
```

#### Package façade update

Export `wallet_router` from `app/api/__init__.py`.

### UI

Export a Bearer-authenticated fetch helper from `frontend/src/api/client.ts` (today `authenticatedFetch` is module-private). Prefer exporting it (or a thin `apiFetch` alias) so `walletClient.ts` does not duplicate token handling.

Create `frontend/src/types/wallet.ts`:

```typescript
export type BalanceItem = {
  asset: string
  available: string
}

export type BalanceList = {
  items: BalanceItem[]
}
```

Create `frontend/src/api/walletClient.ts`:

```typescript
import { ApiError, authenticatedFetch } from './client'
import type { BalanceList } from '../types/wallet'

async function parseErrorResponse(response: Response): Promise<ApiError> {
  try {
    const envelope = (await response.json()) as {
      code: string
      message: string
    }
    return new ApiError(response.status, envelope)
  } catch {
    return new ApiError(response.status, {
      code: 'INTERNAL_ERROR',
      message: 'Request failed.',
    })
  }
}

export async function getUserBalances(): Promise<BalanceList> {
  const response = await authenticatedFetch('/me/balances')
  if (!response.ok) {
    throw await parseErrorResponse(response)
  }
  return response.json() as Promise<BalanceList>
}
```

Create `frontend/src/pages/WalletPage.tsx` that loads balances on mount and renders asset + available. Wire logout on this page (reuse `logout` from `client.ts`).

In `frontend/src/App.tsx`, replace the Phase 2 **Authorized** stub (`authStatus === 'authorized'`) with `<WalletPage />` (or navigate to it). Keep the development Admin entry point unchanged.

**Slice 1 checkpoint:** After a Phase 4 admin deposit to the signed-in user, `GET /me/balances` returns that currency's credited amount and the other seeded currency at zero (formatted to catalog precision). Unauthenticated calls return `401 AUTHENTICATION_FAILED`. Wallet page shows balances after login.

## Slice 2 — user transactions

### Domain

Extend `backend/app/domain/ports/repositories/transaction_query_repository.py`:

```python
from uuid import UUID

from ...read_models.pagination import PaginatedResult, PaginationParams
from ...read_models.transaction_list_item import TransactionListItem


class TransactionQueryRepository(Protocol):
    async def get_all_transactions_page(
        self, params: PaginationParams
    ) -> PaginatedResult[TransactionListItem]: ...

    async def get_user_transactions_page(
        self, user_id: UUID, params: PaginationParams
    ) -> PaginatedResult[TransactionListItem]: ...
```

Create `backend/app/domain/use_cases/wallet/list_user_transactions_query.py`:

```python
from dataclasses import dataclass

from ...ports import CurrentUserProvider
from ...ports.repositories.transaction_query_repository import (
    TransactionQueryRepository,
)
from ...read_models.pagination import PaginatedResult, PaginationParams
from ...read_models.transaction_list_item import TransactionListItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class UserTransactionsQuery:
    params: PaginationParams


class UserTransactionsHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        transaction_query_repo: TransactionQueryRepository,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._transaction_query_repo = transaction_query_repo

    async def handle(
        self, query: UserTransactionsQuery
    ) -> Result[PaginatedResult[TransactionListItem]]:
        user = self._current_user_provider.get()
        page = await self._transaction_query_repo.get_user_transactions_page(
            user.id, query.params
        )
        return Result.success(page)
```

#### Package façade update

Export `UserTransactionsHandler` and `UserTransactionsQuery` from domain façades.

### DB

Extend `TransactionQueryRepositoryImpl` with `get_user_transactions_page` using the Phase 3 ownership filter. Prefer a SQLAlchemy formulation equivalent to the CTE (subquery of the user's wallet ids, then `source_wallet_id IN (…) OR dest_wallet_id IN (…)`). Apply the same `ORDER BY created_at DESC, id DESC`, offset/limit, and `total_items` count as `get_all_transactions_page`.

```python
async def get_user_transactions_page(
    self, user_id: UUID, params: PaginationParams
) -> PaginatedResult[TransactionListItem]:
    offset = params.page_number * params.page_size
    wallet_ids = (
        select(UserWalletModel.id).where(UserWalletModel.user_id == user_id)
    ).scalar_subquery()

    ownership = or_(
        TransactionModel.source_wallet_id.in_(wallet_ids),
        TransactionModel.dest_wallet_id.in_(wallet_ids),
    )

    count_stmt = select(func.count()).select_from(TransactionModel).where(ownership)
    total_items = (await self.session.execute(count_stmt)).scalar_one()

    stmt = (
        select(TransactionModel)
        .where(ownership)
        .order_by(
            TransactionModel.created_at.desc(),
            TransactionModel.id.desc(),
        )
        .offset(offset)
        .limit(params.page_size)
    )
    result = await self.session.execute(stmt)
    items = [transaction_to_list_item(row) for row in result.scalars().all()]
    return PaginatedResult(total_items=total_items, items=items)
```

In `dependencies.py`, add `build_list_user_transactions_handler(session, current_user_provider)`.

### API

Add to `wallet.py`:

```python
@router.get(
    "/transactions",
    dependencies=[Depends(bind_current_user)],
)
async def list_user_transactions(
    executor: Annotated[
        ListUserTransactionsExecutor,
        Depends(get_list_user_transactions_executor),
    ],
    page_number: Annotated[int, Query(ge=0)] = 0,
    page_size: Annotated[int, Query(gt=0, le=100)] = 20,
) -> TransactionListResponse:
    page = unwrap_result(
        await executor(
            UserTransactionsQuery(
                PaginationParams(page_number=page_number, page_size=page_size)
            )
        )
    )
    return TransactionListResponse(
        total_items=page.total_items,
        items=[
            TransactionItemResponse(
                id=item.id,
                type=item.type.upper(),
                status=item.status.upper(),
                created_at=item.created_at,
            )
            for item in page.items
        ],
    )
```

Wire the executor in `api/dependencies.py` (read session + `CurrentUserProvider`), mirroring Slice 1.

Emit uppercase `type` / `status` to match admin transaction listing and [API_CONTRACT.md](../API_CONTRACT.md).

### UI

Extend `frontend/src/types/wallet.ts`:

```typescript
export type TransactionItem = {
  id: string
  type: string
  status: string
  created_at: string
}

export type TransactionList = {
  total_items: number
  items: TransactionItem[]
}
```

Add `listUserTransactions(pageNumber?, pageSize?)` to `walletClient.ts` (query string `page_number` / `page_size`).

On `WalletPage`, render a transaction table and a **Load more** button when `transactions.length < total_items`. Increment `page_number` on each load. After a Phase 4 deposit that credited this user, the newest row shows `DEPOSIT` / `COMPLETED`. Slice 6 adds **Asset** and **Amount** columns (see below).

**Slice 2 checkpoint:** `GET /me/transactions` returns only transactions where the current user owns the source or destination wallet, newest first, with `total_items` for Load more. Another user's deposits do not appear.

## Slice 3 — exchange

### Domain

`INSUFFICIENT_FUNDS` already exists in `domain/error_codes.py`. No new domain error constants are required for exchange validation beyond Phase 4 codes.

Extend `backend/app/domain/ports/repositories/user_wallet_command_repository.py`:

```python
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from ...entities import UserWallet


class UserWalletCommandRepository(Protocol):
    async def get_or_create_for_update(
        self, user_id: UUID, currency_id: UUID, wallet_id: UUID, now: datetime
    ) -> UserWallet: ...

    async def lock_for_update_ordered(
        self, wallet_ids: Sequence[UUID]
    ) -> list[UserWallet]: ...

    async def credit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> None: ...

    async def debit(
        self, wallet_id: UUID, amount: Decimal, now: datetime
    ) -> bool: ...
```

`debit` returns `True` when the row was updated, `False` when the balance was insufficient (no row matched `amount >= :amt`).

Create `backend/app/domain/use_cases/wallet/exchange_cmd.py`:

```python
from dataclasses import dataclass
from uuid import UUID, uuid4

from ...entities import Transaction
from ...error_codes import (
    INVALID_AMOUNT,
    INVALID_PRECISION,
    INSUFFICIENT_FUNDS,
    UNSUPPORTED_ASSET,
)
from ...ports import (
    ClockService,
    CurrencyQueryRepository,
    CurrentUserProvider,
    TransactionCommandRepository,
    UserWalletCommandRepository,
)
from ...result import Result
from ...value_objects.money import Money


@dataclass(frozen=True, slots=True)
class ExchangeCommand:
    source_asset_label: str
    destination_asset_label: str
    amount_str: str


@dataclass(frozen=True, slots=True)
class ExchangeResult:
    transaction_id: UUID


class ExchangeHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        transactions_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._transactions_repo = transactions_repo
        self._clock_service = clock_service

    async def handle(self, command: ExchangeCommand) -> Result[ExchangeResult]:
        source_label = command.source_asset_label.strip().upper()
        dest_label = command.destination_asset_label.strip().upper()
        if source_label == dest_label:
            return Result.failure(INVALID_AMOUNT)

        source_currency = await self._currency_query_repo.get_by_label(source_label)
        dest_currency = await self._currency_query_repo.get_by_label(dest_label)
        if source_currency is None or dest_currency is None:
            return Result.failure(UNSUPPORTED_ASSET)

        try:
            # Source precision + 1:1 amount must also fit destination precision.
            # Validate both before any wallet lock (Phase 4 deposit rule).
            money = Money.parse(
                source_label, command.amount_str, source_currency.precision
            )
            Money.parse(dest_label, command.amount_str, dest_currency.precision)
        except ValueError as error:
            message = str(error)
            if "precision" in message:
                return Result.failure(INVALID_PRECISION)
            if "positive" in message or "Invalid amount" in message:
                return Result.failure(INVALID_AMOUNT)
            return Result.failure(UNSUPPORTED_ASSET)

        user = self._current_user_provider.get()
        now = self._clock_service.now()

        source_wallet = await self._user_wallets_repo.get_or_create_for_update(
            user.id, source_currency.id, uuid4(), now
        )
        dest_wallet = await self._user_wallets_repo.get_or_create_for_update(
            user.id, dest_currency.id, uuid4(), now
        )
        await self._user_wallets_repo.lock_for_update_ordered(
            [source_wallet.id, dest_wallet.id]
        )

        debited = await self._user_wallets_repo.debit(
            source_wallet.id, money.amount, now
        )
        if not debited:
            return Result.failure(INSUFFICIENT_FUNDS)

        await self._user_wallets_repo.credit(dest_wallet.id, money.amount, now)
        transaction_id = uuid4()
        await self._transactions_repo.add(
            Transaction(
                id=transaction_id,
                type="exchange",
                source_wallet_id=source_wallet.id,
                source_amount=money.amount,
                dest_wallet_id=dest_wallet.id,
                dest_amount=money.amount,
                status="completed",
                created_at=now,
            )
        )
        return Result.success(ExchangeResult(transaction_id=transaction_id))
```

#### Package façade update

Export `ExchangeHandler`, `ExchangeCommand`, `ExchangeResult` from domain façades.

### DB

Extend `UserWalletCommandRepositoryImpl`:

```python
async def lock_for_update_ordered(
    self, wallet_ids: Sequence[UUID]
) -> list[UserWallet]:
    ordered_ids = sorted(set(wallet_ids))
    stmt = (
        select(UserWalletModel)
        .where(UserWalletModel.id.in_(ordered_ids))
        .order_by(UserWalletModel.id.asc())
        .with_for_update()
    )
    result = await self.session.execute(stmt)
    return [user_wallet_to_domain(row) for row in result.scalars().all()]

async def debit(
    self, wallet_id: UUID, amount: Decimal, now: datetime
) -> bool:
    stmt = (
        update(UserWalletModel)
        .where(
            UserWalletModel.id == wallet_id,
            UserWalletModel.amount >= amount,
        )
        .values(
            amount=UserWalletModel.amount - amount,
            updated_at=now,
        )
    )
    result = await self.session.execute(stmt)
    return result.rowcount > 0
```

In `dependencies.py`, add `build_exchange_handler(session, current_user_provider)` wiring currency query repo, user wallet command repo, transaction command repo, and clock (same collaborators as admin deposit plus `CurrentUserProvider`).

### API

Map `INSUFFICIENT_FUNDS` in `api/exception_handlers.py`:

```python
"INSUFFICIENT_FUNDS": (
    status.HTTP_409_CONFLICT,
    "The available balance is insufficient for this operation.",
),
```

Extend `backend/app/api/schemas/wallet.py` with mutation DTOs (or a dedicated `me.py` schema module if preferred — keep wallet-related shapes together unless the file grows unwieldy):

```python
from uuid import UUID

from pydantic import BaseModel, Field


class ExchangeRequest(BaseModel):
    source_asset: str = Field(max_length=6)
    destination_asset: str = Field(max_length=6)
    amount: str


class WalletMutationResponse(BaseModel):
    id: UUID
    type: str
    status: str = "COMPLETED"
```

Add route:

```python
@router.post(
    "/exchanges",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(bind_current_user)],
)
async def create_exchange(
    body: ExchangeRequest,
    executor: Annotated[ExchangeExecutor, Depends(get_exchange_executor)],
) -> WalletMutationResponse:
    data = unwrap_result(
        await executor(
            ExchangeCommand(
                source_asset_label=body.source_asset,
                destination_asset_label=body.destination_asset,
                amount_str=body.amount,
            )
        )
    )
    return WalletMutationResponse(id=data.transaction_id, type="EXCHANGE")
```

Wire `get_exchange_executor` to open `session.begin()`, inject `get_current_user_provider()`, call `build_exchange_handler`, and invoke the handler.

### UI

Add exchange types and `createExchange({ source_asset, destination_asset, amount })` to the wallet client.

On `WalletPage`, add an exchange form:

- source and destination `<select>` from `GET /reference/currencies` using Bearer auth (add `listReferenceCurrencies` to `walletClient` via `authenticatedFetch`, or share a small reference helper — do not require the admin key);
- amount text input;
- on success refresh balances and prepend/reload transactions; show standard error envelope messages (`INVALID_PRECISION`, `INSUFFICIENT_FUNDS`, etc.).

**Slice 3 checkpoint:** Exchanging `1.0000` USDT→USD debits USDT and credits USD by the same amount; a `completed` `exchange` row has both wallet FKs set. Same-asset exchange or excess USD fractional digits returns `422`. Spending more than available returns `409 INSUFFICIENT_FUNDS`.

## Slice 4 — withdrawal

### Domain

Create `backend/app/domain/ports/repositories/admin_wallet_command_repository.py`:

```python
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID


class AdminWalletCommandRepository(Protocol):
    async def get_for_update(self, currency_id: UUID) -> None: ...

    async def credit(
        self, currency_id: UUID, amount: Decimal, now: datetime
    ) -> None: ...
```

Version 1 does not require a domain `AdminWallet` entity; the command port locks and credits by `currency_id` only.

Create `backend/app/domain/use_cases/wallet/withdraw_cmd.py`:

```python
from dataclasses import dataclass
from uuid import UUID, uuid4

from ...entities import Transaction
from ...error_codes import (
    INVALID_AMOUNT,
    INVALID_PRECISION,
    INSUFFICIENT_FUNDS,
    UNSUPPORTED_ASSET,
)
from ...ports import (
    ClockService,
    CurrencyQueryRepository,
    CurrentUserProvider,
    TransactionCommandRepository,
    UserWalletCommandRepository,
)
from ...ports.repositories.admin_wallet_command_repository import (
    AdminWalletCommandRepository,
)
from ...result import Result
from ...value_objects.money import Money


@dataclass(frozen=True, slots=True)
class WithdrawCommand:
    asset_label: str
    amount_str: str


@dataclass(frozen=True, slots=True)
class WithdrawResult:
    transaction_id: UUID


class WithdrawHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        admin_wallets_repo: AdminWalletCommandRepository,
        transactions_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._admin_wallets_repo = admin_wallets_repo
        self._transactions_repo = transactions_repo
        self._clock_service = clock_service

    async def handle(self, command: WithdrawCommand) -> Result[WithdrawResult]:
        currency = await self._currency_query_repo.get_by_label(
            command.asset_label.strip().upper()
        )
        if currency is None:
            return Result.failure(UNSUPPORTED_ASSET)
        try:
            money = Money.parse(
                command.asset_label, command.amount_str, currency.precision
            )
        except ValueError as error:
            message = str(error)
            if "precision" in message:
                return Result.failure(INVALID_PRECISION)
            if "positive" in message or "Invalid amount" in message:
                return Result.failure(INVALID_AMOUNT)
            return Result.failure(UNSUPPORTED_ASSET)

        user = self._current_user_provider.get()
        now = self._clock_service.now()

        # Lock order: user wallet, then admin wallet row.
        wallet = await self._user_wallets_repo.get_or_create_for_update(
            user.id, currency.id, uuid4(), now
        )
        await self._admin_wallets_repo.get_for_update(currency.id)

        debited = await self._user_wallets_repo.debit(wallet.id, money.amount, now)
        if not debited:
            return Result.failure(INSUFFICIENT_FUNDS)

        await self._admin_wallets_repo.credit(currency.id, money.amount, now)
        transaction_id = uuid4()
        await self._transactions_repo.add(
            Transaction(
                id=transaction_id,
                type="withdrawal",
                source_wallet_id=wallet.id,
                source_amount=money.amount,
                dest_wallet_id=None,
                dest_amount=money.amount,
                status="completed",
                created_at=now,
            )
        )
        return Result.success(WithdrawResult(transaction_id=transaction_id))
```

#### Package façade update

Export `AdminWalletCommandRepository`, `WithdrawHandler`, `WithdrawCommand`, `WithdrawResult`.

### DB

Create `backend/app/db/repositories/admin_wallet_command_repository.py`:

```python
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update

from app.domain import AdminWalletCommandRepository

from ..models import AdminWalletModel
from ..session import AsyncSession


class AdminWalletCommandRepositoryImpl(AdminWalletCommandRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_update(self, currency_id: UUID) -> None:
        stmt = (
            select(AdminWalletModel)
            .where(AdminWalletModel.currency_id == currency_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        result.scalar_one()  # seeded in Phase 3; missing row is a programming error

    async def credit(
        self, currency_id: UUID, amount: Decimal, now: datetime
    ) -> None:
        stmt = (
            update(AdminWalletModel)
            .where(AdminWalletModel.currency_id == currency_id)
            .values(
                amount=AdminWalletModel.amount + amount,
                updated_at=now,
            )
        )
        await self.session.execute(stmt)
```

Wire `build_withdraw_handler` in `dependencies.py`.

#### Package façade update

Export `AdminWalletCommandRepositoryImpl` from db façades.

### API

Extend schemas:

```python
class WithdrawRequest(BaseModel):
    asset: str = Field(max_length=6)
    amount: str
```

Add route:

```python
@router.post(
    "/withdrawals",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(bind_current_user)],
)
async def create_withdrawal(
    body: WithdrawRequest,
    executor: Annotated[WithdrawExecutor, Depends(get_withdraw_executor)],
) -> WalletMutationResponse:
    data = unwrap_result(
        await executor(
            WithdrawCommand(asset_label=body.asset, amount_str=body.amount)
        )
    )
    return WalletMutationResponse(id=data.transaction_id, type="WITHDRAWAL")
```

Wire `get_withdraw_executor` with `session.begin()` + `CurrentUserProvider`, same pattern as exchange.

### UI

Add `createWithdrawal({ asset, amount })` to `walletClient`.

On `WalletPage`, add a withdrawal form (asset select from reference currencies, amount input). On success refresh user balances and history.

Optional manual check: open Admin page and confirm `GET /admin/balances` increased for the withdrawn asset.

**Slice 4 checkpoint:** Withdrawal debits the user wallet, credits the matching `admin_wallets` row, and inserts a `completed` withdrawal with `dest_wallet_id = NULL`. Insufficient funds returns `409`. Admin balances are no longer all zero after a successful withdrawal.

## Slice 5 — transfer

### Domain

Create `backend/app/domain/use_cases/wallet/transfer_cmd.py`:

```python
from dataclasses import dataclass
from uuid import UUID, uuid4

from ...entities import Transaction
from ...error_codes import (
    INVALID_AMOUNT,
    INVALID_PRECISION,
    INSUFFICIENT_FUNDS,
    UNSUPPORTED_ASSET,
    USER_NOT_FOUND,
)
from ...ports import (
    ClockService,
    CurrencyQueryRepository,
    CurrentUserProvider,
    TransactionCommandRepository,
    UserCommandRepository,
    UserWalletCommandRepository,
)
from ...result import Result
from ...value_objects.money import Money


@dataclass(frozen=True, slots=True)
class TransferCommand:
    recipient_email: str
    asset_label: str
    amount_str: str


@dataclass(frozen=True, slots=True)
class TransferResult:
    transaction_id: UUID


class TransferHandler:
    def __init__(
        self,
        current_user_provider: CurrentUserProvider,
        user_cmd_repo: UserCommandRepository,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        transactions_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        self._current_user_provider = current_user_provider
        self._user_cmd_repo = user_cmd_repo
        self._currency_query_repo = currency_query_repo
        self._user_wallets_repo = user_wallets_repo
        self._transactions_repo = transactions_repo
        self._clock_service = clock_service

    async def handle(self, command: TransferCommand) -> Result[TransferResult]:
        email = command.recipient_email.strip().casefold()
        currency = await self._currency_query_repo.get_by_label(
            command.asset_label.strip().upper()
        )
        if currency is None:
            return Result.failure(UNSUPPORTED_ASSET)
        try:
            money = Money.parse(
                command.asset_label, command.amount_str, currency.precision
            )
        except ValueError as error:
            message = str(error)
            if "precision" in message:
                return Result.failure(INVALID_PRECISION)
            if "positive" in message or "Invalid amount" in message:
                return Result.failure(INVALID_AMOUNT)
            return Result.failure(UNSUPPORTED_ASSET)

        sender = self._current_user_provider.get()
        if email == sender.email.casefold():
            return Result.failure(INVALID_AMOUNT)

        recipient = await self._user_cmd_repo.get_by_normalized_email(email)
        if recipient is None:
            return Result.failure(USER_NOT_FOUND)

        now = self._clock_service.now()
        source_wallet = await self._user_wallets_repo.get_or_create_for_update(
            sender.id, currency.id, uuid4(), now
        )
        dest_wallet = await self._user_wallets_repo.get_or_create_for_update(
            recipient.id, currency.id, uuid4(), now
        )
        await self._user_wallets_repo.lock_for_update_ordered(
            [source_wallet.id, dest_wallet.id]
        )

        debited = await self._user_wallets_repo.debit(
            source_wallet.id, money.amount, now
        )
        if not debited:
            return Result.failure(INSUFFICIENT_FUNDS)

        await self._user_wallets_repo.credit(dest_wallet.id, money.amount, now)
        transaction_id = uuid4()
        await self._transactions_repo.add(
            Transaction(
                id=transaction_id,
                type="transfer",
                source_wallet_id=source_wallet.id,
                source_amount=money.amount,
                dest_wallet_id=dest_wallet.id,
                dest_amount=money.amount,
                status="completed",
                created_at=now,
            )
        )
        return Result.success(TransferResult(transaction_id=transaction_id))
```

Reuse `UserCommandRepository.get_by_normalized_email` from Phase 4 (no `FOR UPDATE` on the user row — same as deposit recipient lookup).

#### Package façade update

Export `TransferHandler`, `TransferCommand`, `TransferResult`.

### DB

No new repository types beyond Slice 3 extensions. Wire `build_transfer_handler` in `dependencies.py` with `UserCommandRepositoryImpl`, currency query repo, user wallet command repo, transaction command repo, clock, and `CurrentUserProvider`.

### API

Extend schemas:

```python
from pydantic import BaseModel, EmailStr, Field


class TransferRequest(BaseModel):
    email: EmailStr
    asset: str = Field(max_length=6)
    amount: str
```

Add route:

```python
@router.post(
    "/transfers",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(bind_current_user)],
)
async def create_transfer(
    body: TransferRequest,
    executor: Annotated[TransferExecutor, Depends(get_transfer_executor)],
) -> WalletMutationResponse:
    data = unwrap_result(
        await executor(
            TransferCommand(
                recipient_email=str(body.email),
                asset_label=body.asset,
                amount_str=body.amount,
            )
        )
    )
    return WalletMutationResponse(id=data.transaction_id, type="TRANSFER")
```

Wire `get_transfer_executor` with `session.begin()` + `CurrentUserProvider`.

### UI

Add `listReferenceUsers` and `listReferenceCurrencies` to `walletClient` via `authenticatedFetch` (Bearer JWT), mirroring admin client response types but without `X-Admin-Key`.

Add `createTransfer({ email, asset, amount })`.

On `WalletPage`, add a transfer form:

- recipient `<select>` from `GET /reference/users` — display **email only**, submit `email` (not `user_id`); exclude the current user's email from the list when the client knows it (optional UX; server still rejects self-transfer);
- currency `<select>` from reference currencies;
- amount input;
- on success refresh balances and history for the sender.

**Slice 5 checkpoint:** Transfer moves the amount from sender to recipient in the same currency; both users see the `TRANSFER` / `COMPLETED` row in their history; unknown email returns `404 USER_NOT_FOUND`; self-transfer returns `422 INVALID_AMOUNT`.

## Slice 6 — transaction list enrichment and UI layout

Follow-up polish after Slices 1–5: enrich admin and user transaction list responses with display amount and asset, fix wallet/reference integration bugs found during manual testing, and align the wallet and admin page layouts.

### Domain

Extend `backend/app/domain/read_models/transaction_list_item.py`:

```python
@dataclass(frozen=True, slots=True)
class TransactionListItem:
    id: UUID
    type: str
    status: str
    created_at: datetime
    amount: Decimal
    source_asset: str | None
    dest_asset: str | None
```

Display **amount** (backend; same rule for all types):

- If `source_wallet_id` is `NULL` or `source_amount == 0` → use `dest_amount` (deposits).
- Otherwise → use `source_amount` (withdrawals, exchanges, transfers).

Pass through **currency labels** from joined wallet rows as `source_asset` / `dest_asset` (`None` when that side has no user wallet, e.g. deposit source). Do not compute a combined display label in the domain or DB layer.

**Asset column display (frontend only):**

| Type | UI **Asset** column |
| --- | --- |
| deposit | `dest_asset` |
| withdrawal | `source_asset` |
| transfer | `source_asset` (same currency both sides) |
| exchange | `` `${source_asset}/${dest_asset}` `` |

Implement in `frontend/src/utils/transaction.ts` as `formatTransactionAsset(type, source_asset, dest_asset)`.

### DB

Update `backend/app/db/mappers/transaction.py` — `transaction_to_list_item` accepts optional `source_asset` / `dest_asset` labels from joined wallet rows, selects display amount, and stores both labels on `TransactionListItem` unchanged.

Extend `TransactionQueryRepositoryImpl` (`backend/app/db/repositories/transaction_query_repository.py`):

- Add `_list_item_select()` with `OUTER JOIN` on source/dest `user_wallets` and `currencies` (aliased) so each row carries currency labels.
- Use the enriched select in both `get_all_transactions_page` and `get_user_transactions_page` (user filter unchanged).

No new repository ports; only mapper and existing query impl changes.

### API

Extend `TransactionItemResponse` in `backend/app/api/schemas/wallet.py`:

```python
class TransactionItemResponse(BaseModel):
    id: UUID
    type: str
    status: str
    source_asset: str | None = None
    dest_asset: str | None = None
    amount: str
    created_at: datetime
```

In both `api/routers/wallet.py` (`list_user_transactions`) and `api/routers/admin.py` (`list_admin_transactions`):

- Inject `ListCurrenciesExecutor` alongside the transaction executor.
- Build `precision_by_label` from `CurrenciesQuery`.
- Map each item with `format_asset_amount_wtih_precision(item.amount, map_not_null_asset_label(item.source_asset, item.dest_asset), precision_by_label)` (`map_not_null_asset_label` in `api/formatting.py` prefers source label, else dest).
- Keep uppercase `type` / `status`. Response exposes raw `source_asset` / `dest_asset`; combined labels are a UI concern.

**Reference auth fix (required for wallet page):** In `api/dependencies.py`, `require_admin_or_user_auth` must declare `credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]` **without** `= None` as the parameter default (FastAPI otherwise skips dependency injection and Bearer JWT is ignored → `401` on `/reference/*` from the wallet UI). Place `credentials` before optional `x_admin_key` to satisfy Python parameter ordering. This function is shared with Phase 4 reference routes; the fix applies to both admin-key and Bearer callers.

### UI

#### Shared layout (`frontend/src/App.css`)

Add `.wallet-page` (max-width 960px, top-aligned, full-width sections) — do **not** reuse narrow `.auth` centering for wallet/admin operator pages; tall content vertically centered in `.auth` appears blank.

Reuse `.wallet-section`, `.wallet-operation-card`, `.wallet-operations` (grid for three user forms), and `.wallet-actions` from the wallet page.

#### Email normalization (`frontend/src/utils/email.ts`)

Browsers do not reliably support `String.prototype.casefold()`. Add:

```typescript
export function normalizeEmail(value: string | null | undefined): string | undefined
```

using `trim().toLowerCase()`. Use in `WalletPage` for self-transfer recipient filtering — never call `casefold()` in frontend code.

In `frontend/src/api/client.ts`:

- Export `authenticatedFetch`.
- On successful `verifyOtp`, store normalized email in `sessionStorage` as `user_email` (optional UX: exclude self from transfer recipient list; cleared on logout and on `401`).

#### Wallet page layout (`frontend/src/pages/WalletPage.tsx`)

Section order after login:

1. **Balances** table (Asset / Available) — same columns as admin balances widget.
2. **Operations** row — Exchange, Withdraw, Transfer cards (`wallet-operations` grid; stacks on narrow viewports).
3. **Transaction history** table — columns: **Type**, **Asset**, **Amount**, **Status**, **Created** (one value per column). **Asset** uses `formatTransactionAsset(type, source_asset, dest_asset)` (single label or `SOURCE/DEST` for exchange).
4. **Load more**, dev admin link, **Logout**.

Load balances/transactions and reference data on independent paths so a reference failure still shows balances when possible.

Root element: `<main className="wallet-page">`.

#### Admin page layout (`frontend/src/pages/AdminPage.tsx`)

Align with wallet page width and section order (Phase 4 UI touch documented here because it shares wallet widgets):

1. Admin API key form (unchanged entry point).
2. **Balances** table (same Asset / Available widget as user page).
3. **Deposit** card (`wallet-operation-card` — currency, recipient, amount, submit).
4. **Transaction history** table (same five columns as wallet history).
5. **Back to app** in `wallet-actions`.

Root element: `<main className="wallet-page">`.

#### Types

Extend `TransactionItem` in both `frontend/src/types/wallet.ts` and `frontend/src/types/admin.ts` with `source_asset`, `dest_asset`, and `amount`. Add `frontend/src/utils/transaction.ts` with `formatTransactionAsset`. Render **Asset** via that helper in wallet and admin transaction tables.

**Slice 6 checkpoint:** `GET /me/transactions` and `GET /admin/transactions` return `source_asset`, `dest_asset`, and catalog-formatted `amount` per row. UI **Asset** column shows one label or `SOURCE/DEST` for exchanges. Wallet and admin pages show wide top-aligned layout; transaction tables have separate Type / Asset / Amount / Status / Created columns. Logged-in wallet page loads `/reference/*` with Bearer JWT without `401`. No frontend `casefold()` usage.

## Final verification

Prerequisites: PostgreSQL is healthy, wallet migration `d377d8c90992` is applied, Phase 4 admin deposit works, the backend runs on port 8000, the frontend runs on port 5173, and at least two users exist from Phase 2 OTP registration (sender + transfer recipient).

- [ ] Missing or invalid Bearer token on `/me/*` returns `401 AUTHENTICATION_FAILED`.
- [ ] After an admin deposit to user A, `GET /me/balances` (as A) shows the credited amount; other catalog currencies appear at zero with correct precision.
- [ ] `GET /me/transactions` paginates with `page_number` / `page_size` / `total_items`; A's deposit appears; user B does not see A's deposit.
- [ ] Exchange USDT→USD (and USD→USDT) at 1:1 updates both balances and inserts a `completed` exchange row with both wallet FKs set; transaction history **Asset** column shows `USDT/USD` or `USD/USDT`.
- [ ] Exchange with same source and destination asset returns `422 INVALID_AMOUNT`.
- [ ] Exchange/withdraw/transfer with excess fractional digits for the asset returns `422 INVALID_PRECISION`.
- [ ] Exchange/withdraw/transfer above available balance returns `409 INSUFFICIENT_FUNDS`.
- [ ] Withdrawal debits the user wallet, credits `admin_wallets` for that currency, and inserts a withdrawal with `dest_wallet_id = NULL`.
- [ ] `GET /admin/balances` reflects the withdrawn amount (non-zero for that asset).
- [ ] Transfer by recipient email credits B and debits A; both histories show the transfer; unknown email returns `404 USER_NOT_FOUND`.
- [ ] Self-transfer returns `422 INVALID_AMOUNT`.
- [ ] Wallet UI replaces the Authorized stub: balances, history with Load more, exchange, withdrawal, and transfer forms work with the signed-in JWT.
- [ ] Wallet and admin pages use the wide `wallet-page` layout (balances → operations/deposit → transaction history); transaction tables show separate Type, Asset, Amount, Status, and Created columns.
- [ ] `GET /me/transactions` and `GET /admin/transactions` include `source_asset`, `dest_asset`, and formatted `amount` on each item; UI **Asset** column shows single label or exchange pair.
- [ ] Transfer/exchange currency and recipient selectors use `GET /reference/*` with Bearer JWT (no admin key required for the user Wallet page).
- [ ] Unexpected command exceptions roll back the transaction; validation failures occur before wallet locks when practical.
- [ ] Concurrent manual double-spend attempts cannot drive wallet amounts negative (spot-check until Phase 7).
- [ ] No JWT, admin key, or OTP appears in logs.

Static quality checks (ruff, mypy, frontend lint/typecheck) pass.

Run static quality checks only; automated tests remain outside this phase.

Validate (read-only; use in CI or before merge):

```sh
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app

cd ../frontend
yarn lint
yarn typecheck
```

Apply fixes (safe auto-fixes for lint; formatter for layout). Run these when checks fail, then re-run the validate commands above:

```sh
cd backend
uv run ruff check . --fix
uv run ruff format .

cd ../frontend
yarn lint --fix
```

Notes:

- `ruff check` and `ruff format` are separate: the formatter reflows code (indentation, quotes, line breaks) but does not fix lint rules such as import order (`I`), naming (`N`), or annotations (`ANN`). Use `ruff check . --fix` for auto-fixable lint issues.
- Some violations (for example long comments over `line-length`, or rules without autofix) still require manual edits after running the fix commands.
- Config lives in `backend/pyproject.toml` (`line-length`, rule `select`, excludes).

## What comes next

[PHASE_6_KAFKA.md](PHASE_6_KAFKA.md) evolves wallet mutations to asynchronous Kafka processing (Version 2).
