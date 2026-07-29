# Clean Architecture Wallet — Technical Requirements

## 1. Purpose

This is a learning sample of a Python web application for a developer experienced in C#, JavaScript, SQL, and Solidity. The developer implements the sample; AI supplies planning, explanations, review, and diagnosis when requested.

The product behavior is defined in [FUNCTIONAL_REQUIREMENTS.md](FUNCTIONAL_REQUIREMENTS.md). This document defines the technical architecture and constraints for implementing version 1 and version 2. [README.md](README.md) defines document authority and reading order.

## 2. Technology stack

### 2.1 Backend

- Python `>=3.14,<3.15`
- FastAPI with OpenAPI/Swagger UI
- Pydantic and `pydantic-settings`
- SQLAlchemy 2.0 async ORM with `asyncpg`
- PostgreSQL
- Alembic configuration and migrations under `backend/`
- PyJWT with HS256 Bearer access tokens
- `uv` for Python versions, environments, dependencies, and locking
- `ruff` for linting and formatting
- `mypy` with strict mode; do not use the deprecated SQLAlchemy mypy plugin
- pytest, pytest-asyncio, and HTTPX
- `testcontainers` with its PostgreSQL extra for PostgreSQL integration tests
- `email-validator` for Pydantic email validation

Password hashing and `passlib` are not needed because authentication is OTP-only.

### 2.2 Frontend

- Vite 8 with `@vitejs/plugin-react` 6
- React 19
- TypeScript
- React Router 8
- Native `fetch` through a small typed API client
- Plain CSS
- ESLint for linting, Vitest and React Testing Library for a minimal set of UI tests
- Yarn, activated with `corepack enable`; npm must not be used for frontend installation or scripts
- `frontend/.yarnrc.yml` sets `nodeLinker: node-modules`, so resolved frontend packages are installed in `frontend/node_modules`

No component library, global state library, or generated API client is required for the sample.

### 2.3 Version 2 messaging

- Apache Kafka 4.3
- `aiokafka>=0.14,<0.15` as the async Python Kafka client
- Transactional outbox and duplicate-safe inbox/message processing
- One wallet command topic partitioned by target user ID
- One command worker process with deposit, exchange, and withdrawal handlers

Kafka and the worker are introduced only in version 2.

### 2.4 Local development

- Backend and frontend run locally with hot reload.
- PostgreSQL runs through Docker Compose from version 1.
- Version 2 extends Docker Compose with Kafka and the command worker.
- Application secrets and connection settings come from `backend/.env`; safe examples live in `backend/.env.example`.
- Configuration, profile boundaries, local ports, topic names, and polling defaults are defined in [CONFIGURATION.md](CONFIGURATION.md).

### 2.5 Supported-version and dependency policy

The scaffold declares direct dependencies with bounded compatible ranges and commits the resolved `backend/uv.lock` and `frontend/yarn.lock`. The lockfiles, not a floating package installation, define a reproducible build.

- The current baseline is Python 3.14.6, FastAPI 0.139.2, Pydantic 2.13.4, `pydantic-settings` 2.14.2, SQLAlchemy 2.0.51, `uv` 0.11.31, `testcontainers` 4.14.2, `email-validator` 2.3.0, and `aiokafka` 0.14.0.
- PostgreSQL 18.4 is the supported database baseline. Pin Compose to an exact patch tag and upgrade after backup/restore and integration-test verification.
- Apache Kafka 4.3.1 is the broker baseline. Pin its image to an exact patch tag or immutable digest.
- The frontend baseline is Node.js 22.22 or later supported LTS, Vite 8, React 19.2, React Router 8, and the latest compatible Vitest and Testing Library releases resolved by Yarn.
- Enable Corepack before frontend setup with `corepack enable`, then use `yarn install --immutable`. Yarn's download cache remains an implementation detail; `nodeLinker: node-modules` is the required setting that stores the installed package tree in `frontend/node_modules`.
- Check supported Python versions and release notes for every direct-dependency upgrade, update a dedicated lockfile change, scan dependencies for known vulnerabilities, and run the complete quality suite before merging.
- Review dependency versions at least monthly and apply security updates on an expedited path. Major-version upgrades require explicit compatibility tests and documented migration notes.

## 3. Architecture

### 3.1 Style

Use Hexagonal Architecture with a logical CQRS split:

- the domain and use-case layer is framework-independent;
- incoming adapters translate HTTP or Kafka messages into commands/queries;
- outgoing ports describe persistence, token, OTP, clock, and messaging needs;
- PostgreSQL, FastAPI, PyJWT, and Kafka are outer adapters;
- command handlers mutate state and return `Result[T]`;
- query handlers return `Result[T]` containing dedicated frozen read models and never mutate state.

CQRS does not mean event sourcing, separate databases, or a mediator library. Commands and queries use different ports and models but share PostgreSQL.

Use cases remain nested under `domain/use_cases/` rather than introducing a top-level `application/` package.

### 3.2 Dependency rule

`domain/` must not import FastAPI, Pydantic, SQLAlchemy, PyJWT, or Kafka packages. Dependencies point inward:

```
api / kafka worker ──> domain commands and queries <── ports
db / auth / messaging adapters ──────────────────────> ports
```

Domain ports use `typing.Protocol`. Manual provider functions in `app/dependencies.py` compose concrete adapters; no DI container is used.

### 3.3 Target folder structure

```
project-root/
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .env
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── domain/
│   │   │   ├── entities/
│   │   │   ├── value_objects/
│   │   │   │   └── money.py
│   │   │   ├── enums.py
│   │   │   ├── current_user.py
│   │   │   ├── error_codes.py
│   │   │   ├── result.py
│   │   │   ├── read_models.py
│   │   │   ├── ports/
│   │   │   │   ├── command_repositories.py
│   │   │   │   ├── current_user_provider.py
│   │   │   │   ├── query_repositories.py
│   │   │   │   ├── services.py
│   │   │   │   └── messaging.py
│   │   │   └── use_cases/
│   │   │       ├── commands/
│   │   │       └── queries/
│   │   ├── api/
│   │   │   ├── current_user_provider.py
│   │   │   ├── routers/
│   │   │   │   ├── auth.py
│   │   │   │   ├── wallet.py
│   │   │   │   └── admin.py
│   │   │   ├── schemas/
│   │   │   ├── mappers.py
│   │   │   ├── exception_handlers.py
│   │   │   └── result_mapping.py
│   │   ├── auth/
│   │   │   ├── jwt_service.py
│   │   │   └── otp_service.py
│   │   ├── db/
│   │   │   ├── models.py
│   │   │   ├── mappers.py
│   │   │   ├── session.py
│   │   │   └── repositories/
│   │   │       ├── user_repository.py
│   │   │       ├── auth_repository.py
│   │   │       ├── command_repositories.py
│   │   │       └── query_repositories.py
│   │   ├── messaging/                 # version 2
│   │   │   ├── contracts.py
│   │   │   ├── kafka_adapter.py
│   │   │   ├── outbox_relay.py
│   │   │   └── worker.py
│   │   └── kafka_api/                 # version 2, removable diagnostics adapter
│   │       ├── router.py
│   │       ├── schemas.py
│   │       ├── service.py
│   │       └── repository.py
│   ├── scripts/
│   └── tests/
│       ├── unit/
│       └── integration/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── pages/
│   │   ├── components/
│   │   └── types/
│   └── package.json
└── docs/
```

Files may be split further when they become large, but layer boundaries and dependency direction must remain unchanged.

## 4. Domain model

### 4.1 Identity and ownership

- `User.id` is a UUID.
- Each user may hold at most one wallet per currency (`user_wallets` row keyed by `user_id` + `currency_id`).
- Admin custody is represented by `admin_wallets` — one row per currency.
- Admin API-key access is not represented as a user role.
- Other persisted entities use UUIDs where they cross process boundaries.

### 4.2 Money

`Money` is a framework-free value object containing a currency label and `Decimal` amount.

- PostgreSQL stores amounts as fixed-precision `NUMERIC`, never float.
- A suitable common column type is `NUMERIC(28, 8)`.
- Per-currency decimal precision is defined in the `currencies` table (`precision` column). Initial seed: USD 4, USDT 8.
- Values must be positive for commands and non-negative for wallet balances.
- Mapping and validation must not silently round.
- A 1:1 exchange must be exactly representable at the destination currency's precision.

### 4.3 Wallets and balances

User balances live on `user_wallets.amount`. Admin balances live on `admin_wallets.amount`.

- Version 1 stores a single amount per wallet row.
- Version 2 may add balance buckets or equivalent columns — strategy TBD when Kafka work starts ([PHASE_6_KAFKA.md](implementation/PHASE_6_KAFKA.md)).
- Missing `user_wallets` rows may be represented as zero by query read models; command repositories create rows when a mutation requires them.
- Supported assets are rows in `currencies`, initially USD and USDT.

### 4.4 Business transactions

Transaction types are `deposit`, `exchange`, `withdrawal`, and `transfer`. The transfer HTTP API is implemented in Phase 5 (Version 1).

Each row records a transfer between wallet endpoints: nullable `source_wallet_id` and `dest_wallet_id` reference `user_wallets.id`; NULL means admin/system (mint on deposit, sink on withdrawal). `source_amount` and `dest_amount` are always populated.

The operation's financial terms are immutable after creation. Its lifecycle status may transition through controlled methods:

- version 1: `completed` or `failed`;
- version 2: additional statuses such as `pending`, `rejected`.

User transaction history is scoped by wallet ownership (`source_wallet_id` or `dest_wallet_id` in the user's wallet IDs). Phase 5 query repositories use a CTE + `IN` pattern (see [PHASE_3_WALLET_SCHEMA.md](implementation/PHASE_3_WALLET_SCHEMA.md)). Admin transaction listing queries all rows.

### 4.5 Authentication entities

- `OtpChallenge`: user ID, email, keyed OTP digest, expiry, failed-attempt count, consumed/invalidated timestamps.
- `AuthSession`: `jti`, user ID, expiry, created timestamp, and optional revoked timestamp.
- `CurrentUser`: frozen dataclass with user ID, normalized email, and the current authentication-session `jti`. A later user-lifecycle phase may add and enforce active state.

OTP digests use a keyed one-way digest so the six-digit value is not stored in plain text. Random OTP generation uses Python's `secrets` module.

## 5. CQRS use cases

### 5.1 Commands

Commands are plain dataclasses and handlers are async. Handlers depend only on domain types and outgoing ports. Every handler returns `Result[T]`, using `Result[None]` when success has no payload.

Version 1 command handlers include:

- request OTP;
- verify OTP and create auth session;
- revoke current auth session;
- create immediate admin deposit;
- execute immediate exchange;
- execute immediate withdrawal.

Version 2 separates submission from execution for wallet mutations:

- HTTP submission handlers create a pending transaction and outbox command;
- deposit submission also increments the pending balance;
- worker execution handlers perform current-state validation and balance transitions;
- worker handlers finalize transaction and message state with guarded duplicate-safe transitions.

### 5.2 Queries

Query handlers return `Result[T]` containing frozen, use-case-specific read models:

- current user's balances;
- admin balances;
- current user's paginated transactions;
- admin's paginated all-user transactions;
- operation status;
- Kafka diagnostics messages through the isolated diagnostics module.

Query repositories project only required columns. They do not load write aggregates merely to shape responses.

### 5.3 Result contract

`domain/result.py` defines one immutable, generic `Result[T]` used by every command and query handler:

- `Result.success(data: T | None = None)` creates a successful result;
- `Result.failure(error_code: str, reason: Exception | None = None)` creates a failed result;
- read-only properties expose `is_success`, `data`, `error_code`, and `reason`;
- a successful result has no error code or reason;
- a failed result has a non-empty error code and no data;
- post-initialization validation enforces these invariants and raises `ValueError("Invalid Result initialization.")` for an invalid combination.

Expected business, authorization, and not-found outcomes return `Result.failure(...)`. Error codes are stable machine-readable strings defined centrally rather than repeated as ad hoc literals. The optional `reason` is internal diagnostic context: it is never serialized, exposed to clients, or logged automatically.

Unexpected infrastructure and programming failures are not converted to `Result.failure`. They propagate as exceptions so the active transaction rolls back and the API or worker can apply its unexpected-failure policy.

## 6. Persistence and transactions

### 6.1 ORM separation

Domain entities, Pydantic DTOs, and SQLAlchemy ORM models are separate:

- API mapping lives under `api/`;
- persistence mapping lives under `db/`;
- ORM instrumentation and Pydantic models never enter domain handlers.

### 6.2 Transaction boundary

Use one async SQLAlchemy session per HTTP command or consumed Kafka message:

1. open the session and `session.begin()` transaction context;
2. execute all repositories for the command using that session;
3. return `Result.success(...)` or `Result.failure(...)` normally so the context commits;
4. allow unexpected exceptions to escape so the context rolls back;
5. close the session always.

The session dependency, command executor, or worker message scope supplies the transaction boundary. Domain handlers depend directly on repository Protocols and do not receive SQLAlchemy sessions or a custom Unit of Work. Every repository participating in one command shares the same session.

A failed `Result` is an expected outcome, not a transaction failure. Therefore, any changes made before returning it are committed and must be intentional. OTP verification relies on this rule: a wrong attempt increments the counter and returns `Result.failure("OTP_INVALID")` or `Result.failure("OTP_LOCKED")`; normal transaction exit commits the increment. Wallet handlers perform business validation under their locks before mutation unless a persisted rejection is explicitly part of the use case.

### 6.3 Concurrency

Balance-changing handlers:

- lock all affected wallet rows with `SELECT ... FOR UPDATE`;
- acquire locks in deterministic order (by wallet `id` or `(user_id, currency_id)` as appropriate);
- check funds after locks are acquired;
- update wallet amounts and transaction history in the same database transaction.

Integration tests must cover concurrent debit attempts and prove that balances cannot become negative.

Authentication handlers also require concurrency control. Request and verification operations lock the normalized user's row before changing challenges. First-time user creation uses `INSERT ... ON CONFLICT` followed by `SELECT ... FOR UPDATE`, and the database enforces at most one current challenge per user where both `consumed_at` and `invalidated_at` are null.

### 6.4 Initial schema

Version 1 requires tables for:

- users;
- currencies;
- user wallets;
- admin wallets;
- business transactions;
- OTP challenges;
- authentication sessions.

Version 2 adds:

- outbox messages;
- inbox/processed messages;
- Kafka message diagnostics records, or equivalent operational columns that support the diagnostics queries.

All schema changes use reviewed Alembic migrations.

## 7. Authentication and authorization

### 7.1 OTP

- Email is normalized consistently before lookup.
- Requesting a new OTP invalidates earlier active challenges.
- OTP is six digits, valid for 5 minutes, single-use, and limited to 5 failed attempts.
- The OTP is returned only when `APP_ENV=development` and `ENABLE_DEMO_OTP=true`; it must not appear in logs or Kafka diagnostics.

### 7.2 JWT

- PyJWT, HS256, Bearer header only.
- Claims include `sub`, `jti`, and `exp`.
- JWT expiry and secret come from settings.
- Decode failures become `Result.failure("AUTHENTICATION_FAILED", reason=...)` rather than leaking PyJWT exceptions.

### 7.3 Current-user pipeline

1. FastAPI `HTTPBearer(auto_error=False)` extracts the token without advertising an OAuth2 password flow.
2. `TokenService` validates and decodes it.
3. The auth-session repository confirms that `jti` is active.
4. The user repository loads fresh user state.
5. The current-user query returns a frozen `CurrentUser` containing the session `jti`.
6. The API binds that value to the request-scoped current-user provider before invoking protected handlers and resets the binding in `finally`.

Logout revokes only the current `jti`.

`CurrentUser` is a domain value, not a port. `domain/ports/current_user_provider.py` defines the behavior required by authenticated use cases:

```python
class CurrentUserProvider(Protocol):
    def get(self) -> CurrentUser: ...
```

`api/current_user_provider.py` implements the port with request-scoped `ContextVar` state. Its adapter-only bind/reset operations are not part of the domain Protocol. The authentication dependency binds the validated `CurrentUser`, yields control to the route, and always resets the exact context token afterward. Calling `get()` without a bound user is a wiring error and raises an unexpected exception; it is not an `AUTHENTICATION_FAILED` business result.

Handlers that require an authenticated HTTP principal receive `CurrentUserProvider` through constructor injection and call `get()` when needed. Commands and queries do not repeat `current_user` fields. There is no mutable global current-user singleton, and domain code never imports the API implementation, FastAPI request state, or `ContextVar`.

Only authenticated HTTP use cases use this provider. OTP request/verification, development admin operations, Kafka workers, and other non-request execution paths receive identity explicitly from their own inputs when needed. Do not let detached/background tasks depend on the request provider because Python task creation can copy `ContextVar` state; pass any required identity explicitly instead.

### 7.4 Admin API key

- `/admin/*` endpoints require `X-Admin-Key` only when `APP_ENV=development`.
- The development value comes from `ADMIN_API_KEY`; `x_admin_key` is permitted only as a local `backend/.env.example` placeholder.
- Comparison uses a timing-safe function.
- Admin endpoints do not require a user JWT.
- Static-key admin access is demo-only and must be disabled in production.

### 7.5 Kafka diagnostics

`/kafka/*` diagnostics endpoints require no authentication only when `APP_ENV=development` and `ENABLE_KAFKA_DIAGNOSTICS=true`. They return `404` otherwise. Their payloads must exclude OTPs, JWTs, admin keys, connection strings, and secrets. The module is development-only and removable.

## 8. HTTP API contract

The canonical request/response, pagination, status, error, and compatibility rules are in [API_CONTRACT.md](API_CONTRACT.md). The initial route surface is:

### 8.1 Authentication

- `POST /auth/otp/request`
- `POST /auth/otp/verify`
- `POST /auth/logout`

### 8.2 Reference

- `GET /reference/currencies` — `X-Admin-Key` or Bearer JWT
- `GET /reference/users` — `X-Admin-Key` or Bearer JWT

### 8.3 User wallet

- `GET /me/balances`
- `POST /me/exchanges`
- `POST /me/withdrawals`
- `POST /me/transfers`
- `GET /me/transactions`
- `GET /me/operations/{operation_id}` in version 2

### 8.4 Admin

- `POST /admin/deposits`
- `GET /admin/balances`
- `GET /admin/transactions`
- `GET /admin/operations/{operation_id}` in version 2

### 8.5 Kafka diagnostics

- `GET /kafka/messages`
- `GET /kafka/messages/{message_id}`

### 8.6 Health

- `GET /health/live`
- `GET /health/ready`
- `GET /health/authenticated`

### 8.6 Result unwrapping

`api/result_mapping.py` owns the generic `unwrap_result(result: Result[T]) -> T` helper and an API-layer result exception carrying only `error_code`. For a no-content success, `T` is `None`.

- for success, `unwrap_result` returns `result.data`;
- for failure, it raises the API-layer exception using `result.error_code`;
- it never includes or exposes `result.reason`;
- routers call it only after a transactional command executor has returned, so raising the API-layer exception cannot roll back a committed expected outcome;
- `api/exception_handlers.py` maps the API-layer exception's error code to the status and safe `ErrorEnvelope` message defined in [API_CONTRACT.md](API_CONTRACT.md);
- an unmapped error code is treated as `500 INTERNAL_ERROR`, not exposed verbatim, and logged as an application defect.

Success status codes remain route-specific (`200`, `201`, `202`, or `204`) and are not selected by `unwrap_result`. Request-validation failures bypass `Result[T]` and remain `422 VALIDATION_ERROR`; uncaught exceptions remain `500 INTERNAL_ERROR`.

Version 1 wallet commands return completed results. Version 2 deposit, exchange, and withdrawal submissions return `202 Accepted` and an operation identifier. HTTP idempotency keys are deferred to the roadmap's final optional hardening phase.

Pydantic handles request shape, types, email format, and basic precision. Use cases handle authorization and business rules. The API maps command/query `Result.failure` error codes to HTTP responses in one central location; domain code never imports HTTP types.

## 9. Version 2 messaging

### 9.1 Command envelope

Each command is published to the `wallet.commands.v1` topic and consumed by the `wallet-command-worker-v1` consumer group. Each Kafka command contains:

- schema version;
- unique message ID;
- operation/transaction ID;
- command type;
- target user ID used as partition key;
- causation/correlation IDs;
- creation timestamp;
- typed payload.

Contracts are versioned DTOs and contain no ORM or Pydantic API objects.

### 9.2 Outbox

HTTP submission writes the operation and outbox row atomically. A relay claims unpublished rows, publishes them, and records publication metadata.

Database commit and Kafka publish cannot form one transaction, so delivery is at least once. Inbox uniqueness and guarded state transitions must prevent duplicate application; the system must not claim exactly-once end-to-end behavior.

### 9.3 Worker

- One consumer group processes wallet commands.
- Messages are keyed by target user ID for per-user ordering.
- One worker dispatches to deposit, exchange, and withdrawal execution handlers.
- The worker records processing state before/following execution.
- A duplicate message returns the previously recorded outcome without applying balances again.
- Business rejection and infrastructure failure are distinct states.
- Infrastructure failures remain retryable and do not become AML rejection.

### 9.4 Kafka diagnostics module

`app/kafka_api/` owns only the diagnostics HTTP/query boundary:

- router;
- request/response schemas;
- query service;
- read repository.

It queries PostgreSQL message records, not Kafka directly. Core wallet domain and command handlers do not import this package. Registration in `main.py` is the only application-level dependency, allowing later removal.

## 10. Frontend

The frontend contains Login, Wallet, History, Admin, and version-2 Kafka pages.

- A small API client attaches JWT or admin headers as appropriate.
- JWT and admin key use `sessionStorage` for this demo.
- Protected user routes redirect to Login when no token is present.
- Admin and Kafka pages are development-only; production builds must omit those routes until production authorization and observability controls exist.
- Version 2 polls operation, balance, transaction, and diagnostics queries using the bounded exponential-backoff defaults in [CONFIGURATION.md](CONFIGURATION.md); WebSockets are not required.
- Error responses and pending/rejected/failed statuses are visible in simple text UI.

## 11. Error handling

Expected domain/use-case failures use stable `Result.failure` error codes, for example:

- invalid/expired/consumed OTP;
- invalid/expired/revoked token;
- inactive or missing user;
- unsupported asset;
- invalid amount or precision;
- same source and destination asset;
- insufficient funds;
- invalid balance bucket;
- invalid operation transition.

The API's central error mapping is the sole translation from `Result.failure` codes to HTTP status and safe response messages. The optional `Result.reason` is not part of the HTTP contract. Domain code never imports or raises `HTTPException`.

Worker business failures returned through `Result.failure` become `REJECTED` outcomes with safe reason codes. Unexpected exceptions become `FAILED`, are logged safely, and remain eligible for retry.

## 12. Testing

### 12.1 Unit tests

- Domain entities and `Money` invariants.
- OTP and auth-session behavior.
- Current-user-provider behavior with a fake provider, plus API integration coverage proving request binding is reset and isolated.
- Command handlers with fake command repositories/services, asserting successful and failed `Result` values.
- Query handlers with fake query repositories, asserting successful and failed `Result` values.
- Version 2 state transitions and duplicate-message handling.
- No FastAPI, SQLAlchemy, PostgreSQL, or Kafka is needed.

### 12.2 Integration tests

- PostgreSQL from testcontainers with real Alembic migrations.
- FastAPI through HTTPX.
- OTP request/verify, JWT protection, logout revocation.
- Immediate version-1 deposit/exchange/withdraw flows.
- Decimal precision and concurrent overspending prevention.
- Version-2 outbox publication and worker processing.
- Per-user ordering, duplicate delivery, rejection, retry, and failure cases.
- Kafka diagnostics API projections and secret sanitization.

### 12.3 Frontend tests

Keep UI tests small:

- login flow and token attachment;
- wallet command submission;
- admin-key attachment and deposit form;
- rendering pending/completed/rejected states;
- Kafka diagnostics list.

## 13. Explicit non-goals

- Password authentication, refresh tokens, cookies, or CSRF handling.
- Production OTP delivery/security.
- Real assets, payment rails, wallets, or AML services.
- Event sourcing or separate CQRS databases.
- Generic reusable read models or a mediator/DI framework.
- Exactly-once distributed processing.
- Production-safe public Admin or Kafka diagnostics pages.
- SQLite compatibility.

## 14. Tooling notes

- Configure `ruff` for lint and format in `backend/pyproject.toml`.
- Configure `mypy` with `strict = true`. ORM models must use SQLAlchemy 2.x native `Mapped[...]` annotations and `mapped_column()`.
- Human-driven migration workflow:
  1. change ORM models;
  2. run `uv run alembic revision --autogenerate -m "..."`;
  3. review the generated migration;
  4. run `uv run alembic upgrade head`.
- Pre-commit and CI are optional. They run lint, formatting, type checking, unit tests, integration tests, and the frontend test/build. Version 2 CI additionally runs Kafka outbox, worker, ordering, duplicate-message, and recovery tests.
- [OPERATIONS.md](OPERATIONS.md) defines required health, observability, migration, release, rollback, backup, and incident practices.
