# Phase 3 — Wallet Schema

Add Version 1 wallet persistence: SQLAlchemy ORM models for `currencies`, `user_wallets`, `admin_wallets`, and `transactions`, plus a reviewed Alembic migration that seeds currencies and admin wallets.

Read [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) for carry-forward context. Canonical behavior is defined by [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md), [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md) §4 and §6.4, and [API_CONTRACT.md](../API_CONTRACT.md).

## Current implementation status

- **Authentication schema** complete (migration `23fa0ceb69ca`).
- **Wallet schema** not started.

## Scope

This phase includes:

- ORM models under `backend/app/db/models/` for currencies, user wallets, admin wallets, and business transactions;
- registration of those models on `Base.metadata` via `backend/app/db/models/__init__.py`;
- one Alembic revision creating the four tables, constraints, indexes, and seed rows for currencies and admin wallets.

This phase deliberately excludes:

- domain entities, value objects (`Money`, `Asset`), ports, handlers, mappers, repositories;
- HTTP routes, Pydantic schemas, UI;
- automated tests;
- **all Version 2 schema** (outbox, inbox, Kafka diagnostics, extra balance buckets, extended transaction statuses) — deferred to [PHASE_6_KAFKA.md](PHASE_6_KAFKA.md);
- **`transfer` HTTP API** — the `transfer` transaction type is included in the schema for future use; endpoint and handler work belong to a later phase.

Use manual verification and static quality checks only. Do not add test files during this phase.

## Done when

`uv run alembic upgrade head` applies the new revision on a database that already has authentication tables. PostgreSQL contains `currencies`, `user_wallets`, `admin_wallets`, and `transactions` with the constraints below. Two currency rows (USD, USDT) and two admin wallet rows exist. Backend ruff/mypy pass. No wallet HTTP endpoints exist yet.

## Architecture rules

This phase touches only `backend/app/db/models/` and `backend/alembic/versions/`. Follow existing authentication model conventions ([user.py](../../backend/app/db/models/user.py), [base.py](../../backend/app/db/models/base.py)). Cross-layer rules in [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) apply starting in Phase 4.

## Target layout after this phase

```text
backend/app/db/models/
├── __init__.py          # re-exports wallet models + Base
├── admin_wallet.py      # new
├── auth_session.py      # existing
├── base.py              # existing
├── currency.py          # new
├── otp_challenge.py     # existing
├── transaction.py       # new
├── user_wallet.py       # new
└── user.py              # existing
```

No new packages or directories beyond the four model files.

## Data model summary

```mermaid
erDiagram
    users ||--o{ user_wallets : owns
    currencies ||--o{ user_wallets : denominated_in
    currencies ||--|| admin_wallets : one_per_currency
    user_wallets ||--o{ transactions : source_or_dest
    currencies {
        uuid id PK
        string type "fiat or crypto"
        string name "max 64"
        string label "max 6 unique"
        int precision "decimal places"
    }
    user_wallets {
        uuid id PK
        uuid user_id FK
        uuid currency_id FK
        numeric amount
        timestamptz updated_at
    }
    admin_wallets {
        uuid currency_id PK_FK
        numeric amount
        timestamptz updated_at
    }
    transactions {
        uuid id PK
        string type
        uuid source_wallet_id FK "nullable"
        numeric source_amount
        uuid dest_wallet_id FK "nullable"
        numeric dest_amount
        string status
        timestamptz created_at
    }
```

### Design notes

- **Currencies:** Normalized catalog of supported assets. `precision` defines max decimal places for validation and API formatting. Amount columns use `NUMERIC(28, 8)` regardless of precision — precision governs business rules, not storage width.
- **User wallets:** One row per `(user_id, currency_id)` when it exists. No rows at signup; command handlers in Phase 4/5 create rows on first deposit, exchange, or transfer that needs the target currency. Queries may treat missing currencies as zero balance.
- **Admin wallets:** One row per currency, keyed by `currency_id`. Created eagerly when a currency is seeded. Never referenced by FK from `transactions`; updated by application convention on withdrawal only.
- **Transactions:** Append-only transfer log. `source_wallet_id` and `dest_wallet_id` reference `user_wallets.id`; NULL means admin/system (mint on deposit, sink on withdrawal). Financial fields are immutable after insert; only `status` may change. Version 1 allows `completed` and `failed`. No `completed_at` — a row is final at insert or on allowed status transition.
- **Exchange vs transfer:** Both require two distinct user wallet FKs. Exchange: same user, different currency. Transfer: different users, same currency. Enforced in the application layer (requires join to `user_wallets`).

### Transaction semantics

| Operation | source_wallet_id | dest_wallet_id | amounts | wallet updates |
| --- | --- | --- | --- | --- |
| **Deposit** | `NULL` (mint) | user wallet — create if missing | `source = dest` | credit `user_wallets.amount` |
| **Withdrawal** | user wallet | `NULL` (admin/system) | `source = dest` | debit user; credit `admin_wallets` for that currency |
| **Exchange** | user A wallet (curr X) | user A wallet (curr Y) — create if missing | `source = dest` (1:1) | debit X; credit Y |
| **Transfer** | user A wallet (curr X) | user B wallet (curr X) — create if missing | `source = dest` (1:1) | debit A; credit B |

Deposit **does not debit** admin (matches [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md) §5.1). Only withdrawals move funds into `admin_wallets`.

User transaction history filters via wallet ownership (CTE + `IN` — one row per transaction, no join duplicates):

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

Admin transaction listing queries all rows with the same `ORDER BY`, without the CTE filter.

### Seed data

Use fixed, documented UUIDs so every environment shares the same currency primary keys:

| Label | Type | Precision | UUID |
| --- | --- | --- | --- |
| USD | `fiat` | 4 | `00000000-0000-4000-8000-000000000101` |
| USDT | `crypto` | 8 | `00000000-0000-4000-8000-000000000102` |

Insert currencies and matching `admin_wallets` rows (`amount = 0`) in the migration `upgrade()` within the same transaction.

## Steps

- [ ] Create `backend/app/db/models/currency.py`.

```python
from uuid import UUID

from sqlalchemy import CheckConstraint, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CurrencyModel(Base):
    __tablename__ = "currencies"
    __table_args__ = (
        CheckConstraint(
            "type IN ('fiat', 'crypto')",
            name="ck_currencies_type_valid",
        ),
        CheckConstraint(
            "precision >= 0 AND precision <= 18",
            name="ck_currencies_precision_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    type: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(6), unique=True, nullable=False)
    precision: Mapped[int] = mapped_column(SmallInteger, nullable=False)
```

- [ ] Create `backend/app/db/models/user_wallet.py`.

```python
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UserWalletModel(Base):
    __tablename__ = "user_wallets"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "currency_id",
            name="uq_user_wallets_user_id_currency_id",
        ),
        CheckConstraint("amount >= 0", name="ck_user_wallets_amount_nonnegative"),
        Index("ix_user_wallets_user_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    currency_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
```

- [ ] Create `backend/app/db/models/admin_wallet.py`.

```python
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AdminWalletModel(Base):
    __tablename__ = "admin_wallets"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_admin_wallets_amount_nonnegative"),
    )

    currency_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
```

- [ ] Create `backend/app/db/models/transaction.py`.

```python
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('deposit', 'exchange', 'withdrawal', 'transfer')",
            name="ck_transactions_type_valid",
        ),
        CheckConstraint(
            "status IN ('completed', 'failed')",
            name="ck_transactions_status_v1",
        ),
        CheckConstraint(
            "(type = 'deposit' AND source_wallet_id IS NULL "
            "AND dest_wallet_id IS NOT NULL) OR "
            "(type = 'withdrawal' AND source_wallet_id IS NOT NULL "
            "AND dest_wallet_id IS NULL) OR "
            "(type IN ('exchange', 'transfer') AND source_wallet_id IS NOT NULL "
            "AND dest_wallet_id IS NOT NULL "
            "AND source_wallet_id <> dest_wallet_id)",
            name="ck_transactions_type_wallet_shape",
        ),
        CheckConstraint(
            "source_amount > 0 AND dest_amount > 0",
            name="ck_transactions_amounts_positive",
        ),
        Index(
            "ix_transactions_created_at_id",
            text("created_at DESC"),
            text("id DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_wallet_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_wallets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    dest_wallet_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_wallets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    dest_amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
```

Phase 6 extends allowed statuses. Exchange/transfer cross-wallet rules (same user vs different user, same vs different currency) are enforced in command handlers, not SQL CHECK constraints.

- [ ] Update `backend/app/db/models/__init__.py` to register wallet models on `Base.metadata`.

```python
from .admin_wallet import AdminWalletModel
from .auth_session import AuthSessionModel
from .base import Base
from .currency import CurrencyModel
from .otp_challenge import OtpChallengeModel
from .transaction import TransactionModel
from .user import UserModel
from .user_wallet import UserWalletModel

__all__ = [
    "AdminWalletModel",
    "AuthSessionModel",
    "Base",
    "CurrencyModel",
    "OtpChallengeModel",
    "TransactionModel",
    "UserModel",
    "UserWalletModel",
]
```

Do not re-export wallet models from `app.db` façade yet unless another layer needs them in this phase. The façade update for repositories belongs in Phase 4.

- [ ] Generate the Alembic revision from `backend/`.

```sh
cd backend
uv run alembic revision --autogenerate -m "add wallet tables"
```

- [ ] Review the generated revision manually. Confirm it includes:

  - all four tables with constraints and indexes named as in the models above;
  - `down_revision` pointing at `23fa0ceb69ca`;
  - no accidental drops or changes to authentication tables.

- [ ] Add currency and admin wallet seeds to `upgrade()` after table creation. Use a fixed timestamp for reproducibility (UTC):

```python
CURRENCY_USD_ID = "00000000-0000-4000-8000-000000000101"
CURRENCY_USDT_ID = "00000000-0000-4000-8000-000000000102"
SEED_UPDATED_AT = "2026-01-01T00:00:00+00:00"

def upgrade() -> None:
    # ... autogenerated create_table calls ...
    op.execute(
        sa.text(
            """
            INSERT INTO currencies (id, type, name, label, precision)
            VALUES
                (:usd_id, 'fiat', 'US Dollar', 'USD', 4),
                (:usdt_id, 'crypto', 'Tether USD', 'USDT', 8)
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(usd_id=CURRENCY_USD_ID, usdt_id=CURRENCY_USDT_ID)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO admin_wallets (currency_id, amount, updated_at)
            VALUES
                (:usd_id, 0, :updated_at),
                (:usdt_id, 0, :updated_at)
            ON CONFLICT (currency_id) DO NOTHING
            """
        ).bindparams(
            usd_id=CURRENCY_USD_ID,
            usdt_id=CURRENCY_USDT_ID,
            updated_at=SEED_UPDATED_AT,
        )
    )
```

If autogenerate wraps `upgrade()` differently, place the seed after all `create_table` calls. Use `op.get_bind().execute(...)` if your revision style prefers that over `op.execute`.

- [ ] Implement `downgrade()` to drop wallet tables in dependency order: `transactions`, then `user_wallets`, then `admin_wallets`, then `currencies`. Do not drop authentication tables.

- [ ] Apply the migration.

```sh
cd backend
uv run alembic upgrade head
```

- [ ] Verify static quality gates.

```sh
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

Apply fixes if needed:

```sh
cd backend
uv run ruff check . --fix
uv run ruff format .
```

- [ ] Verify schema in PostgreSQL (Postgres container must be running).

```sh
docker exec py-hex-aied-2-postgres-1 psql -U wallet_user -d wallet_db -c "\dt"
```

Expected tables include `currencies`, `user_wallets`, `admin_wallets`, and `transactions` alongside existing auth tables.

```sh
docker exec py-hex-aied-2-postgres-1 psql -U wallet_user -d wallet_db -c "
SELECT label, type, precision FROM currencies ORDER BY label;"
```

Expected: USD (fiat, precision 4) and USDT (crypto, precision 8).

```sh
docker exec py-hex-aied-2-postgres-1 psql -U wallet_user -d wallet_db -c "
SELECT c.label, aw.amount
FROM admin_wallets aw
JOIN currencies c ON c.id = aw.currency_id
ORDER BY c.label;"
```

Expected: two rows, both with `amount = 0`.

```sh
docker exec py-hex-aied-2-postgres-1 psql -U wallet_user -d wallet_db -c "
SELECT conname
FROM pg_constraint
WHERE conrelid = 'user_wallets'::regclass
ORDER BY conname;"
```

Confirm `uq_user_wallets_user_id_currency_id` and `ck_user_wallets_amount_nonnegative` exist.

## Final verification checklist

- [ ] `currencies`, `user_wallets`, `admin_wallets`, and `transactions` exist with Version 1 constraints only.
- [ ] USD and USDT currencies are seeded with correct precision values.
- [ ] Admin wallets exist for both currencies with zero balance.
- [ ] No domain, repository, mapper, API, or UI files were added.
- [ ] No Version 2 tables or extended status values beyond `completed`/`failed` were introduced.
- [ ] `uv run alembic upgrade head` is idempotent on an already-migrated database.
- [ ] ruff and mypy pass.

## What comes next

[PHASE_4_ADMIN_WALLET.md](PHASE_4_ADMIN_WALLET.md) introduces domain logic, repositories, admin deposit, admin balances/transactions queries, HTTP routes, and admin UI — the first full vertical slice on top of this schema.
