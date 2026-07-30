# Phase 4 — Admin Wallet

Complete Slice 0 configuration first, then implement admin wallet features end to end in five vertical feature slices, in this exact order:

1a. `reference-currencies`
1b. `reference-users`
2. `admin-deposit`
3. `admin-balances`
4. `admin-transactions`

Within each feature slice, work in the strict order **Domain → DB → API → UI**. Do not run or demonstrate a feature slice until all four sections in that slice are complete.

Read [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) for architecture rules and [PHASE_3_WALLET_SCHEMA.md](PHASE_3_WALLET_SCHEMA.md) for the wallet tables this phase builds on.

## Current implementation status

- **Phase 3 wallet schema** complete (migration `d377d8c90992`).
- **Slice 0** not started.
- **Slice 1a** not started.
- **Slice 1b** not started.
- **Slice 2** not started.
- **Slice 3** not started.
- **Slice 4** not started.
- **Final verification** not started.

Canonical behavior is defined by [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md), [API_CONTRACT.md](../API_CONTRACT.md), [CONFIGURATION.md](../CONFIGURATION.md), and [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md). Those documents and this guide are aligned on the phase-specific scope below.

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
- HTTP admin and reference routes and Pydantic schemas;
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

Request/response shapes: [API_CONTRACT.md](../API_CONTRACT.md) § Reference and § Admin.

### Out of scope

- User wallet routes (`/me/*`) — Phase 5;
- User-to-user `transfer` HTTP API — schema-ready in Phase 3; implement when scoped;
- Kafka / async behavior — Phase 6;
- automated tests — Phase 7.

## Done when

An operator can open the Admin page in development, enter admin key, load the currency list and user list for the deposit selectors, submit a deposit to a selected user email, see the deposit in admin transaction history, and see admin balances (still zero for currencies not yet received via withdrawal). Invalid admin key returns `403 ADMIN_ACCESS_DENIED`. Backend ruff/mypy and frontend lint/typecheck pass.

## Architecture rules

Follow [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) § Architectural invariants. Phase 4 adds:

- separate command vs query repository Protocols per entity concern;
- reference routes accept admin key **or** Bearer JWT; admin routes accept admin key only;
- wallet mutations use one `AsyncSession.begin()` per command; query routes use short-lived read sessions without an explicit write transaction;
- `Money` precision comes from the `currencies` catalog; no silent rounding.

## Shared implementation notes

This section is reference material, not an implementation stage. It contains no create/update step. Complete file contents and schema definitions appear in Slice 0–4 at the point they are created or updated, preserving the Domain → DB → API → UI order.

### Target layout

Use this final target layout as a reference only. Phase 3 ORM models already exist under `backend/app/db/models/`.

```text
backend/
└── app/
    ├── dependencies.py              # extend with wallet handler builders
    ├── main.py                      # register reference + admin routers (dev gate)
    ├── api/
    │   ├── dependencies.py          # require_reference_auth, require_admin_key, executors
    │   ├── exception_handlers.py    # extend ERROR_RESPONSES with wallet codes
    │   ├── routers/
    │   │   ├── reference.py         # Slice 1a/1b
    │   │   └── admin.py             # Slice 2–4
    │   └── schemas/
    │       ├── data_list.py         # shared DataList[T] envelope
    │       ├── reference.py
    │       ├── admin.py
    │       └── wallet.py            # shared balance/transaction shapes
    ├── db/
    │   ├── mappers/
    │   │   ├── currency.py
    │   │   ├── user_wallet.py
    │   │   ├── admin_wallet.py
    │   │   └── transaction.py
    │   └── repositories/
    │       ├── currency_repository.py
    │       ├── user_repository.py   # extend existing
    │       ├── user_wallet_repository.py
    │       ├── transaction_repository.py
    │       └── admin_wallet_repository.py
    └── domain/
        ├── error_codes.py           # extend in Slice 2
        ├── value_objects/
        │   ├── asset.py             # Slice 2
        │   └── money.py             # Slice 2
        ├── entities/
        │   ├── currency.py          # Slice 2
        │   ├── user_wallet.py       # Slice 2
        │   └── transaction.py       # Slice 2
        ├── read_models/
        │   ├── currency_catalog_item.py   # Slice 1a
        │   ├── user_reference_item.py     # Slice 1b
        │   ├── balance_item.py            # Slice 3
        │   └── transaction_list_item.py   # Slice 4
        ├── ports/repositories/
        │   ├── currency_repository.py
        │   ├── user_repository.py
        │   ├── user_wallet_repository.py
        │   ├── transaction_repository.py
        │   └── admin_wallet_repository.py
        └── use_cases/
            ├── currency/list_currencies_query.py
            ├── user/list_users_query.py
            ├── admin/admin_deposit_cmd.py
            ├── admin/get_admin_balances_query.py
            └── transaction/list_admin_transactions_query.py

frontend/src/
├── types/admin.ts
├── api/adminClient.ts
└── pages/AdminPage.tsx              # dev-only; or Admin section in App.tsx
```

### Cross-cutting rules

- **Command vs query ports:** command repositories lock and mutate; query repositories project read models only. Concrete classes use the `*Impl` suffix and live under `app/db/repositories/`.
- **Reference auth:** `GET /reference/*` succeeds when either `X-Admin-Key` matches `settings.admin_api_key` (timing-safe compare) **or** the Bearer JWT passes the existing `GetCurrentUserHandler` path.
- **Admin auth:** `POST` and `GET /admin/*` require a valid `X-Admin-Key` only. No user JWT.
- **Deposit semantics:** mint from admin/system (`source_wallet_id = NULL`), credit user wallet, insert one `completed` deposit row; **do not debit** `admin_wallets`.
- **Concurrency:** deposit locks the target user wallet with `SELECT … FOR UPDATE` before credit (future-proofs Phase 5).
- **Cursor pagination:** opaque base64 JSON `{"created_at":"<RFC3339>","id":"<uuid>"}`; repository filters with `(created_at, id) < (:cursor_created_at, :cursor_id)` under `ORDER BY created_at DESC, id DESC`; fetch `limit + 1` rows to detect `next_cursor`; `limit` is 1–100, default 20.

### Error codes introduced incrementally

| Code | HTTP | Introduced in |
| --- | --- | --- |
| `ADMIN_ACCESS_DENIED` | 403 | Slice 2 |
| `USER_NOT_FOUND` | 404 | Slice 2 |
| `UNSUPPORTED_ASSET` | 422 | Slice 2 |
| `INVALID_AMOUNT` | 422 | Slice 2 |
| `INVALID_PRECISION` | 422 | Slice 2 |

Add each code to `domain/error_codes.py` and `api/exception_handlers.py` when the slice that returns it is implemented. Request-shape validation remains Pydantic `422 VALIDATION_ERROR`. `INSUFFICIENT_FUNDS` is defined in Slice 2 for Phase 5 reuse but is not returned by admin deposit in Version 1.

## Slice 0 — configuration

Complete this preparation before Slice 1a. It changes only existing configuration files; do not create directories from the target layout yet.

Confirm `backend/.env.example` and the gitignored `backend/.env` include:

```dotenv
ADMIN_API_KEY=__some__key
```

`backend/app/config.py` already declares `admin_api_key: str | None = None`. No change is required unless the field is missing.

**Slice 0 checkpoint:** `ADMIN_API_KEY` is set in local `.env`; backend starts with Phase 3 migration applied.

## Slice 1a — reference currencies

### Domain

Create `backend/app/domain/read_models/currency_catalog_item.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurrencyCatalogItem:
    label: str
    name: str
    type: str
    precision: int
```

Create `backend/app/domain/ports/repositories/currency_repository.py`:

```python
from typing import Protocol

from ...read_models import CurrencyCatalogItem


class CurrencyQueryRepository(Protocol):
    async def list_all_ordered_by_label(self) -> list[CurrencyCatalogItem]: ...
```

Create `ListCurrenciesQuery` (empty dataclass) and `ListCurrenciesHandler` in `backend/app/domain/use_cases/currency/list_currencies_query.py`:

```python
from dataclasses import dataclass

from ...ports import CurrencyQueryRepository
from ...read_models import CurrencyCatalogItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class ListCurrenciesQuery:
    pass


class ListCurrenciesHandler:
    def __init__(self, currency_query_repo: CurrencyQueryRepository) -> None:
        self._currency_query_repo = currency_query_repo

    async def handle(
        self, _: ListCurrenciesQuery
    ) -> Result[list[CurrencyCatalogItem]]:
        items = await self._currency_query_repo.list_all_ordered_by_label()
        return Result.success(items)
```

Queries may return an existing domain value directly inside `Result[T]`; no separate `ListCurrenciesResult` wrapper is required.

#### Package façade update

At the end of this Domain section, alter `backend/app/domain/__init__.py`:

```python
from .read_models import CurrencyCatalogItem
from .ports import CurrencyQueryRepository
from .use_cases import ListCurrenciesHandler, ListCurrenciesQuery

__all__ += [
    "CurrencyCatalogItem",
    "CurrencyQueryRepository",
    "ListCurrenciesHandler",
    "ListCurrenciesQuery",
]
```

Re-export `CurrencyCatalogItem` from `read_models/__init__.py` and the handler symbols from `use_cases/__init__.py`.

### DB

Create `backend/app/domain/read_models/__init__.py` if it does not exist.

Create `backend/app/db/mappers/currency.py`:

```python
from app.domain import CurrencyCatalogItem

from ..models import CurrencyModel


def currency_to_catalog_item(model: CurrencyModel) -> CurrencyCatalogItem:
    return CurrencyCatalogItem(
        label=model.label,
        name=model.name,
        type=model.type,
        precision=model.precision,
    )
```

Create `backend/app/db/repositories/currency_repository.py`:

```python
from sqlalchemy import select

from app.domain import CurrencyCatalogItem, CurrencyQueryRepository

from ..mappers import currency_to_catalog_item
from ..models import CurrencyModel
from ..session import AsyncSession


class CurrencyQueryRepositoryImpl(CurrencyQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all_ordered_by_label(self) -> list[CurrencyCatalogItem]:
        stmt = select(CurrencyModel).order_by(CurrencyModel.label.asc())
        result = await self._session.execute(stmt)
        return [currency_to_catalog_item(row) for row in result.scalars().all()]
```

In `backend/app/dependencies.py`, add:

```python
def build_list_currencies_handler(session: AsyncSession) -> ListCurrenciesHandler:
    return ListCurrenciesHandler(CurrencyQueryRepositoryImpl(session))
```

Re-export `CurrencyQueryRepositoryImpl` from `app/db/__init__.py`.

### API

Create `backend/app/api/schemas/data_list.py`:

```python
from pydantic import BaseModel, Field


class DataList[T](BaseModel):
    items: list[T] = Field(default_factory=list)
```

Create `backend/app/api/schemas/reference.py`:

```python
from pydantic import BaseModel


class CurrencyItemResponse(BaseModel):
    label: str
    name: str
    type: str
    precision: int
```

Add reference authentication to `backend/app/api/dependencies.py`. The dependency accepts admin key **or** Bearer JWT:

```python
import secrets
from typing import Annotated

from fastapi import Header, Request

from app.dependencies import build_get_current_user_handler
from app.domain import AUTHENTICATION_FAILED, GetCurrentUserQuery, Result

ADMIN_KEY_HEADER = "X-Admin-Key"


async def require_reference_auth(
    request: Request,
    x_admin_key: Annotated[str | None, Header(alias=ADMIN_KEY_HEADER)] = None,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> None:
    settings = request.app.state.settings
    if x_admin_key is not None and settings.admin_api_key is not None:
        if secrets.compare_digest(x_admin_key, settings.admin_api_key):
            return
    if credentials is not None and credentials.scheme.casefold() == "bearer":
        async with request.app.state.session_factory() as session:
            handler = build_get_current_user_handler(session, settings)
            result = await handler.handle(
                GetCurrentUserQuery(token=credentials.credentials)
            )
            if result.is_success:
                return
    unwrap_result(Result.failure(AUTHENTICATION_FAILED))
```

When both headers are present, admin key is checked first; a valid key short-circuits without JWT validation.

Add read executor and route wiring:

```python
ListCurrenciesExecutor = Callable[
    [ListCurrenciesQuery], Awaitable[Result[list[CurrencyCatalogItem]]]
]


def get_list_currencies_executor(request: Request) -> ListCurrenciesExecutor:
    async def execute(query: ListCurrenciesQuery) -> Result[list[CurrencyCatalogItem]]:
        async with request.app.state.session_factory() as session:
            handler = build_list_currencies_handler(session)
            return await handler.handle(query)

    return execute
```

Create `backend/app/api/routers/reference.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends

from app.domain import ListCurrenciesQuery

from ..dependencies import ListCurrenciesExecutor, get_list_currencies_executor, require_reference_auth
from ..result_mapping import unwrap_result
from ..schemas import CurrencyItemResponse, DataList

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get(
    "/currencies",
    dependencies=[Depends(require_reference_auth)],
)
async def list_currencies(
    executor: Annotated[
        ListCurrenciesExecutor, Depends(get_list_currencies_executor)
    ],
) -> DataList[CurrencyItemResponse]:
    items = unwrap_result(await executor(ListCurrenciesQuery()))
    return DataList(
        items=[
            CurrencyItemResponse(
                label=item.label,
                name=item.name,
                type=item.type,
                precision=item.precision,
            )
            for item in items
        ]
    )
```

Register `reference_router` in `backend/app/main.py` behind the development gate from Slice 0.

#### Package façade update

At the end of this API section, alter `backend/app/api/__init__.py`:

```python
from .routers import reference_router

__all__ += ["reference_router"]
```

### UI

Create `frontend/src/types/admin.ts`:

```typescript
export type DataList<T> = {
  items: T[]
}

export type CurrencyItem = {
  label: string
  name: string
  type: string
  precision: number
}
```

Create `frontend/src/api/adminClient.ts`:

```typescript
import { ApiError } from './client'
import type { CurrencyItem, DataList } from '../types/admin'

const ADMIN_KEY_STORAGE = 'admin_api_key'

export function getAdminKey(): string | null {
  return sessionStorage.getItem(ADMIN_KEY_STORAGE)
}

export function setAdminKey(key: string): void {
  sessionStorage.setItem(ADMIN_KEY_STORAGE, key)
}

export async function adminFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const key = getAdminKey()
  if (!key) {
    throw new Error('Admin key is not set.')
  }
  const headers = new Headers(init.headers)
  headers.set('X-Admin-Key', key)
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  return fetch(`/api${path}`, { ...init, headers })
}

export async function listReferenceCurrencies(): Promise<DataList<CurrencyItem>> {
  const response = await adminFetch('/reference/currencies')
  if (!response.ok) {
    throw await ApiError.fromResponse(response)
  }
  return response.json() as Promise<DataList<CurrencyItem>>
}
```

Configure the Vite dev proxy if not already present so `/api` forwards to the backend.

Create a development-only Admin page shell (`frontend/src/pages/AdminPage.tsx` or an Admin section in `App.tsx`):

- input for admin key; on save call `setAdminKey` and fetch currencies;
- render a simple list of currency labels proving Slice 1a end-to-end;
- gate the page behind `import.meta.env.DEV` or an equivalent development check.

**Slice 1a checkpoint:** `GET /reference/currencies` with a valid admin key returns USD and USDT ordered by `label`. Invalid credentials return `401 AUTHENTICATION_FAILED`. Admin-only route rejection is deferred to Slice 2.

## Slice 1b — reference users

### Domain

Create `backend/app/domain/read_models/user_reference_item.py`:

```python
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserReferenceItem:
    user_id: UUID
    email: str
```

Create `backend/app/domain/ports/repositories/user_repository.py`:

```python
from typing import Protocol

from ...read_models import UserReferenceItem


class UserQueryRepository(Protocol):
    async def list_all_ordered_by_email(self) -> list[UserReferenceItem]: ...
```

Create `ListUsersQuery` and `ListUsersHandler` in `backend/app/domain/use_cases/user/list_users_query.py`:

```python
from dataclasses import dataclass

from ...ports import UserQueryRepository
from ...read_models import UserReferenceItem
from ...result import Result


@dataclass(frozen=True, slots=True)
class ListUsersQuery:
    pass


class ListUsersHandler:
    def __init__(self, user_query_repo: UserQueryRepository) -> None:
        self._user_query_repo = user_query_repo

    async def handle(self, _: ListUsersQuery) -> Result[list[UserReferenceItem]]:
        items = await self._user_query_repo.list_all_ordered_by_email()
        return Result.success(items)
```

Keep this port separate from command `UserRepository` even though both touch the `users` table.

#### Package façade update

At the end of this Domain section, alter `backend/app/domain/__init__.py`:

```python
from .read_models import UserReferenceItem
from .ports import UserQueryRepository
from .use_cases import ListUsersHandler, ListUsersQuery

__all__ += [
    "UserReferenceItem",
    "UserQueryRepository",
    "ListUsersHandler",
    "ListUsersQuery",
]
```

### DB

Create `backend/app/db/repositories/user_repository.py`:

```python
from sqlalchemy import select

from app.domain import UserQueryRepository, UserReferenceItem

from ..models import UserModel
from ..session import AsyncSession


class UserQueryRepositoryImpl(UserQueryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all_ordered_by_email(self) -> list[UserReferenceItem]:
        stmt = select(UserModel.id, UserModel.email).order_by(UserModel.email.asc())
        result = await self._session.execute(stmt)
        return [
            UserReferenceItem(user_id=row.id, email=row.email)
            for row in result.all()
        ]
```

In `backend/app/dependencies.py`, add:

```python
def build_list_users_handler(session: AsyncSession) -> ListUsersHandler:
    return ListUsersHandler(UserQueryRepositoryImpl(session))
```

### API

Extend `backend/app/api/schemas/reference.py`:

```python
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserReferenceItemResponse(BaseModel):
    user_id: UUID
    email: EmailStr
```

Add executor and route to `backend/app/api/routers/reference.py`:

```python
@router.get(
    "/users",
    dependencies=[Depends(require_reference_auth)],
)
async def list_users(
    executor: Annotated[ListUsersExecutor, Depends(get_list_users_executor)],
) -> DataList[UserReferenceItemResponse]:
    items = unwrap_result(await executor(ListUsersQuery()))
    return DataList(
        items=[
            UserReferenceItemResponse(user_id=item.user_id, email=item.email)
            for item in items
        ]
    )
```

Wire `get_list_users_executor` in `api/dependencies.py` mirroring the currencies executor.

### UI

Extend `frontend/src/types/admin.ts`:

```typescript
export type UserReferenceItem = {
  user_id: string
  email: string
}
```

Add to `adminClient.ts`:

```typescript
export async function listReferenceUsers(): Promise<DataList<UserReferenceItem>> {
  const response = await adminFetch('/reference/users')
  if (!response.ok) {
    throw await ApiError.fromResponse(response)
  }
  return response.json() as Promise<DataList<UserReferenceItem>>
}
```

On the Admin page, after saving the admin key, fetch and display user emails. A `<select>` stub populated with emails is sufficient until Slice 2 wires the deposit form.

**Slice 1b checkpoint:** `GET /reference/users` returns users registered via Phase 2 OTP, ordered by `email` ascending. Bearer JWT also succeeds on reference routes.

## Slice 2 — admin deposit

### Domain

Extend `backend/app/domain/error_codes.py`:

```python
ADMIN_ACCESS_DENIED = "ADMIN_ACCESS_DENIED"
USER_NOT_FOUND = "USER_NOT_FOUND"
UNSUPPORTED_ASSET = "UNSUPPORTED_ASSET"
INVALID_AMOUNT = "INVALID_AMOUNT"
INVALID_PRECISION = "INVALID_PRECISION"
INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
```

Create `backend/app/domain/value_objects/asset.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Asset:
    label: str

    @classmethod
    def from_label(cls, label: str) -> "Asset":
        normalized = label.strip().upper()
        if normalized not in {"USD", "USDT"}:
            raise ValueError("Unsupported asset label.")
        return cls(label=normalized)
```

Create `backend/app/domain/value_objects/money.py`:

```python
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .asset import Asset


@dataclass(frozen=True, slots=True)
class Money:
    asset: Asset
    amount: Decimal

    @classmethod
    def parse(
        cls, asset_label: str, amount_str: str, precision: int
    ) -> "Money":
        asset = Asset.from_label(asset_label)
        try:
            amount = Decimal(amount_str)
        except InvalidOperation as error:
            raise ValueError("Invalid amount.") from error
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        exponent = amount.as_tuple().exponent
        scale = -exponent if exponent < 0 else 0
        if scale > precision:
            raise ValueError("Amount exceeds asset precision.")
        return cls(asset=asset, amount=amount)
```

Create domain entities aligned with Phase 3 columns in `backend/app/domain/entities/currency.py`, `user_wallet.py`, and `transaction.py`. Example `UserWallet`:

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserWallet:
    id: UUID
    user_id: UUID
    currency_id: UUID
    amount: Decimal
    updated_at: datetime
```

Extend command `UserRepository` in `backend/app/domain/ports/repositories/user_repository.py`:

```python
async def get_by_normalized_email(self, email: str) -> User | None: ...
```

Create command ports:

```python
# user_wallet_repository.py
async def get_or_create_for_update(
    self, user_id: UUID, currency_id: UUID, wallet_id: UUID, now: datetime
) -> UserWallet: ...

async def credit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> None: ...


# transaction_repository.py
async def add(self, transaction: Transaction) -> None: ...


# currency_repository.py — extend for command path
async def get_by_label(self, label: str) -> Currency | None: ...
```

Alternatively, add `CurrencyCommandRepository` with `get_by_label` if you prefer strict command/query separation for currencies. The handler needs label lookup during deposit.

Create `AdminDepositCommand`, `AdminDepositResult`, and `AdminDepositHandler` in `backend/app/domain/use_cases/admin_deposit/admin_deposit_cmd.py`:

```python
@dataclass(frozen=True, slots=True)
class AdminDepositCommand:
    email: str
    asset_label: str
    amount_str: str


@dataclass(frozen=True, slots=True)
class AdminDepositResult:
    transaction_id: UUID


class AdminDepositHandler:
    def __init__(
        self,
        users_repo: UserRepository,
        currency_query_repo: CurrencyQueryRepository,
        user_wallets_repo: UserWalletCommandRepository,
        transactions_repo: TransactionCommandRepository,
        clock_service: ClockService,
    ) -> None:
        ...

    async def handle(
        self, command: AdminDepositCommand
    ) -> Result[AdminDepositResult]:
        email = command.email.strip().casefold()
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

        user = await self._users_repo.get_by_normalized_email(email)
        if user is None:
            return Result.failure(USER_NOT_FOUND)

        now = self._clock_service.now()
        wallet = await self._user_wallets_repo.get_or_create_for_update(
            user.id, currency.id, uuid4(), now
        )
        await self._user_wallets_repo.credit(wallet.id, money.amount, now)
        transaction_id = uuid4()
        await self._transactions_repo.add(
            Transaction(
                id=transaction_id,
                type="deposit",
                source_wallet_id=None,
                source_amount=money.amount,
                dest_wallet_id=wallet.id,
                dest_amount=money.amount,
                status="completed",
                created_at=now,
            )
        )
        return Result.success(AdminDepositResult(transaction_id=transaction_id))
```

Validation failures return before any wallet lock or mutation, so no partial state is written.

#### Package façade update

Export `Money`, `Asset`, wallet entities, command ports, `AdminDepositCommand`, `AdminDepositResult`, `AdminDepositHandler`, and new error codes from `domain/__init__.py`.

### DB

Create mappers:

- `currency_to_domain` for command-side `Currency` entity (includes `id`, `label`, `precision`, …);
- `user_wallet_to_domain`, `transaction_to_model`, `transaction_to_domain` as needed.

Implement `UserWalletCommandRepositoryImpl`:

```python
async def get_or_create_for_update(
    self, user_id: UUID, currency_id: UUID, wallet_id: UUID, now: datetime
) -> UserWallet:
    stmt = (
        select(UserWalletModel)
        .where(
            UserWalletModel.user_id == user_id,
            UserWalletModel.currency_id == currency_id,
        )
        .with_for_update()
    )
    result = await self._session.execute(stmt)
    model = result.scalar_one_or_none()
    if model is None:
        model = UserWalletModel(
            id=wallet_id,
            user_id=user_id,
            currency_id=currency_id,
            amount=Decimal("0"),
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        locked = await self._session.execute(
            select(UserWalletModel)
            .where(UserWalletModel.id == model.id)
            .with_for_update()
        )
        model = locked.scalar_one()
    return user_wallet_to_domain(model)


async def credit(self, wallet_id: UUID, amount: Decimal, now: datetime) -> None:
    stmt = (
        update(UserWalletModel)
        .where(UserWalletModel.id == wallet_id)
        .values(
            amount=UserWalletModel.amount + amount,
            updated_at=now,
        )
    )
    await self._session.execute(stmt)
```

Implement `TransactionCommandRepositoryImpl.add` with an insert of the domain transaction mapped to `TransactionModel`.

Extend `UserRepositoryImpl` with `get_by_normalized_email` (select by email without `FOR UPDATE` — deposit does not need user-row locking).

Extend `CurrencyQueryRepositoryImpl` with `get_by_label` returning a `Currency` domain entity, or add `CurrencyCommandRepositoryImpl` if keeping ports split.

In `backend/app/dependencies.py`, add:

```python
def build_admin_deposit_handler(
    session: AsyncSession,
) -> AdminDepositHandler:
    return AdminDepositHandler(
        UserRepositoryImpl(session),
        CurrencyQueryRepositoryImpl(session),
        UserWalletCommandRepositoryImpl(session),
        TransactionCommandRepositoryImpl(session),
        SystemClock(),
    )
```

Deposit executes inside `session.begin()` at the API executor layer.

### API

Add admin key dependency to `backend/app/api/dependencies.py`:

```python
from app.domain import ADMIN_ACCESS_DENIED


async def require_admin_key(
    request: Request,
    x_admin_key: Annotated[str | None, Header(alias=ADMIN_KEY_HEADER)] = None,
) -> None:
    settings = request.app.state.settings
    if settings.app_env != "development":
        unwrap_result(Result.failure(ADMIN_ACCESS_DENIED))
    if (
        x_admin_key is None
        or settings.admin_api_key is None
        or not secrets.compare_digest(x_admin_key, settings.admin_api_key)
    ):
        unwrap_result(Result.failure(ADMIN_ACCESS_DENIED))
```

Extend `backend/app/api/exception_handlers.py`:

```python
"ADMIN_ACCESS_DENIED": (
    status.HTTP_403_FORBIDDEN,
    "Admin access denied.",
),
"USER_NOT_FOUND": (
    status.HTTP_404_NOT_FOUND,
    "User not found.",
),
"UNSUPPORTED_ASSET": (
    status.HTTP_422_UNPROCESSABLE_CONTENT,
    "The asset is not supported.",
),
"INVALID_AMOUNT": (
    status.HTTP_422_UNPROCESSABLE_CONTENT,
    "The amount is invalid.",
),
"INVALID_PRECISION": (
    status.HTTP_422_UNPROCESSABLE_CONTENT,
    "The amount precision is invalid.",
),
```

Create `backend/app/api/schemas/admin.py`:

```python
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AdminDepositRequest(BaseModel):
    email: EmailStr
    asset: str = Field(max_length=6)
    amount: str


class AdminDepositResponse(BaseModel):
    id: UUID
    type: str = "DEPOSIT"
    status: str = "COMPLETED"
```

Map domain `transaction_id` to response `id`; emit uppercase `type` and `status` strings per [API_CONTRACT.md](../API_CONTRACT.md).

Create `backend/app/api/routers/admin.py`:

```python
router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/deposits",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_key)],
)
async def create_deposit(
    body: AdminDepositRequest,
    executor: Annotated[
        AdminDepositExecutor, Depends(get_admin_deposit_executor)
    ],
) -> AdminDepositResponse:
    result = await executor(
        AdminDepositCommand(
            email=body.email,
            asset_label=body.asset,
            amount_str=body.amount,
        )
    )
    data = unwrap_result(result)
    return AdminDepositResponse(id=data.transaction_id)
```

Wire `get_admin_deposit_executor` to open `session.begin()`, call `build_admin_deposit_handler`, and invoke the handler.

Register `admin_router` in `main.py` behind the development gate.

#### Package façade update

Export `admin_router` from `app/api/__init__.py`.

### UI

Extend `frontend/src/types/admin.ts` with deposit request/response types.

Add to `adminClient.ts`:

```typescript
export async function AdminDeposit(body: {
  email: string
  asset: string
  amount: string
}): Promise<{ id: string; type: string; status: string }> {
  const response = await adminFetch('/admin/deposits', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw await ApiError.fromResponse(response)
  }
  return response.json()
}
```

On the Admin page, wire the deposit form:

- recipient `<select>` from `listReferenceUsers()` — display **email only**, submit `email`;
- currency `<select>` from `listReferenceCurrencies()` — submit `label` as `asset`;
- amount text input; optionally constrain `step`/`pattern` from selected currency `precision`;
- on submit call `AdminDeposit`; show success message with transaction id or standard error envelope message.

**Slice 2 checkpoint:** Deposit credits the user wallet; a `completed` deposit row exists with `source_wallet_id = NULL`; `admin_wallets` amounts remain zero. Invalid admin key returns `403 ADMIN_ACCESS_DENIED`.

## Slice 3 — admin balances

### Domain

Create `backend/app/domain/read_models/balance_item.py`:

```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BalanceItem:
    asset: str
    available: Decimal
```

Create `GetAdminBalancesQuery` and `GetAdminBalancesHandler` in `backend/app/domain/use_cases/admin/get_admin_balances_query.py`:

```python
class GetAdminBalancesHandler:
    def __init__(
        self, admin_wallet_query_repo: AdminWalletQueryRepository
    ) -> None:
        self._admin_wallet_query_repo = admin_wallet_query_repo

    async def handle(
        self, _: GetAdminBalancesQuery
    ) -> Result[list[BalanceItem]]:
        items = await self._admin_wallet_query_repo.list_all_with_labels()
        return Result.success(items)
```

Create `AdminWalletQueryRepository` port:

```python
async def list_all_with_labels(self) -> list[BalanceItem]: ...
```

#### Package façade update

Export `BalanceItem`, `AdminWalletQueryRepository`, `GetAdminBalancesHandler`, and `GetAdminBalancesQuery` from `domain/__init__.py`.

### DB

Create `backend/app/db/mappers/admin_wallet.py` projecting joined currency label and wallet amount.

Implement `AdminWalletQueryRepositoryImpl`:

```python
async def list_all_with_labels(self) -> list[BalanceItem]:
    stmt = (
        select(CurrencyModel.label, AdminWalletModel.amount)
        .join(AdminWalletModel, AdminWalletModel.currency_id == CurrencyModel.id)
        .order_by(CurrencyModel.label.asc())
    )
    result = await self._session.execute(stmt)
    return [
        BalanceItem(asset=row.label, available=row.amount)
        for row in result.all()
    ]
```

In `backend/app/dependencies.py`, add `build_get_admin_balances_handler(session)`.

### API

Create shared balance schemas in `backend/app/api/schemas/wallet.py`:

```python
from pydantic import BaseModel, Field


class BalanceItemResponse(BaseModel):
    asset: str
    available: str


class BalanceListResponse(BaseModel):
    items: list[BalanceItemResponse] = Field(default_factory=list)
```

Format `available` as a decimal string with scale matching the currency precision (no JSON numbers).

Add to `backend/app/api/routers/admin.py`:

```python
@router.get(
    "/balances",
    dependencies=[Depends(require_admin_key)],
)
async def get_admin_balances(
    executor: Annotated[
        GetAdminBalancesExecutor, Depends(get_get_admin_balances_executor)
    ],
) -> BalanceListResponse:
    items = unwrap_result(await executor(GetAdminBalancesQuery()))
    return BalanceListResponse(
        items=[
            BalanceItemResponse(
                asset=item.asset,
                available=format_amount(item.available, item.asset),
            )
            for item in items
        ]
    )
```

Implement `format_amount` in the API layer or a small shared helper that looks up precision from the catalog item list.

### UI

Add `getAdminBalances()` to `adminClient.ts`. On the Admin page, render a balances table (asset + available). After a Slice 2 deposit, all admin amounts remain `"0"` / `"0.0000"` / `"0.00000000"` as appropriate.

**Slice 3 checkpoint:** `GET /admin/balances` returns one row per seeded currency with zero available amounts before any Phase 5 withdrawal.

## Slice 4 — admin transactions

### Domain

Create `backend/app/domain/read_models/transaction_list_item.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TransactionListItem:
    id: UUID
    type: str
    status: str
    created_at: datetime
```

Create pagination types in `backend/app/domain/read_models/pagination.py`:

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PaginationParams:
    limit: int
    cursor: str | None


@dataclass(frozen=True, slots=True)
class PaginatedResult(Generic[T]):
    items: list[T]
    next_cursor: str | None
```

Create `ListAdminTransactionsQuery` carrying `PaginationParams` and `ListAdminTransactionsHandler` in `backend/app/domain/use_cases/transaction/list_admin_transactions_query.py`:

```python
class ListAdminTransactionsHandler:
    def __init__(
        self, transaction_query_repo: TransactionQueryRepository
    ) -> None:
        self._transaction_query_repo = transaction_query_repo

    async def handle(
        self, query: ListAdminTransactionsQuery
    ) -> Result[PaginatedResult[TransactionListItem]]:
        page = await self._transaction_query_repo.list_admin_page(
            query.params.limit, query.params.cursor
        )
        return Result.success(page)
```

Create `TransactionQueryRepository` port:

```python
async def list_admin_page(
    self, limit: int, cursor: str | None
) -> PaginatedResult[TransactionListItem]: ...
```

Cursor encoding/decoding may live in the repository implementation or a small domain helper; keep HTTP opaqueness at the API boundary.

#### Package façade update

Export pagination read models, `TransactionListItem`, `TransactionQueryRepository`, `ListAdminTransactionsHandler`, and `ListAdminTransactionsQuery` from `domain/__init__.py`.

### DB

Implement cursor helpers in `backend/app/db/repositories/transaction_repository.py` (or `backend/app/db/pagination.py`):

```python
import base64
import json
from datetime import datetime
from uuid import UUID


def encode_cursor(created_at: datetime, row_id: UUID) -> str:
    payload = {"created_at": created_at.isoformat(), "id": str(row_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
```

Implement `TransactionQueryRepositoryImpl.list_admin_page`:

```python
async def list_admin_page(
    self, limit: int, cursor: str | None
) -> PaginatedResult[TransactionListItem]:
    stmt = select(TransactionModel).order_by(
        TransactionModel.created_at.desc(),
        TransactionModel.id.desc(),
    )
    if cursor is not None:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(
            (TransactionModel.created_at < cursor_created_at)
            | (
                (TransactionModel.created_at == cursor_created_at)
                & (TransactionModel.id < cursor_id)
            )
        )
    stmt = stmt.limit(limit + 1)
    result = await self._session.execute(stmt)
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [transaction_to_list_item(row) for row in page_rows]
    next_cursor = None
    if has_more:
        last = page_rows[-1]
        next_cursor = encode_cursor(last.created_at, last.id)
    return PaginatedResult(items=items, next_cursor=next_cursor)
```

In `backend/app/dependencies.py`, add `build_list_admin_transactions_handler(session)`.

### API

Reuse or extend `backend/app/api/schemas/wallet.py`:

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionItemResponse(BaseModel):
    id: UUID
    type: str
    status: str
    created_at: datetime


class TransactionListResponse(BaseModel):
    items: list[TransactionItemResponse] = Field(default_factory=list)
    next_cursor: str | None = None
```

Add query parameters to `GET /admin/transactions`:

```python
@router.get(
    "/transactions",
    dependencies=[Depends(require_admin_key)],
)
async def list_admin_transactions(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
    executor: Annotated[
        ListAdminTransactionsExecutor,
        Depends(get_list_admin_transactions_executor),
    ] = ...,
) -> TransactionListResponse:
    page = unwrap_result(
        await executor(
            ListAdminTransactionsQuery(
                PaginationParams(limit=limit, cursor=cursor)
            )
        )
    )
    return TransactionListResponse(
        items=[
            TransactionItemResponse(
                id=item.id,
                type=item.type.upper(),
                status=item.status.upper(),
                created_at=item.created_at,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
    )
```

### UI

Add `listAdminTransactions(limit?, cursor?)` to `adminClient.ts`. On the Admin page, render a transaction table and a **Load more** button when `next_cursor` is non-null. After Slice 2 deposit, the newest row shows `DEPOSIT` / `COMPLETED`.

**Slice 4 checkpoint:** Paginated all-user history includes the deposit from Slice 2, sorted newest first with stable tie-breaker on `id`.

## Final verification

Prerequisites: PostgreSQL is healthy, wallet migration `d377d8c90992` is applied, the backend runs on port 8000, the frontend runs on port 5173, and at least one user exists from Phase 2 OTP registration.

- [ ] `GET /reference/currencies` returns USD and USDT ordered by `label` with admin key or Bearer JWT.
- [ ] `GET /reference/users` returns registered users ordered by `email` with admin key or Bearer JWT.
- [ ] Missing or invalid credentials on reference routes return `401 AUTHENTICATION_FAILED`.
- [ ] Missing or invalid admin key on `/admin/*` returns `403 ADMIN_ACCESS_DENIED`.
- [ ] Deposit to a selected email credits the user wallet; `admin_wallets` amounts stay zero.
- [ ] Deposit with a fifth decimal place for USD returns `422 INVALID_PRECISION`.
- [ ] Deposit with unknown asset returns `422 UNSUPPORTED_ASSET`.
- [ ] Deposit to unknown email returns `404 USER_NOT_FOUND`.
- [ ] `GET /admin/balances` lists all seeded currencies with zero available amounts before Phase 5 withdrawals.
- [ ] `GET /admin/transactions` paginates; the deposit appears newest-first.
- [ ] Admin UI stores the key in `sessionStorage` only; no `ADMIN_API_KEY` in frontend build env.
- [ ] Unexpected command exceptions roll back the transaction; validation failures occur before wallet locks.
- [ ] No admin key, JWT, or OTP appears in logs.

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

[PHASE_5_USER_WALLET.md](PHASE_5_USER_WALLET.md) adds user exchange, withdrawal, balances, and transaction history — completing Version 1 synchronous wallet behavior.
