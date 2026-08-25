# Archived: wallet sample requirements proposal

> **Status: historical and non-authoritative.** This proposal is retained only to explain prior design decisions. Do not use it to implement new behavior. The canonical requirements are the documentation index, functional requirements, technical requirements, API contract, configuration, operations, and implementation steps.
>
> **Version 1 alignment (2026-08-01):** The Version 1 section below was reviewed against the implemented codebase and corrected where it had drifted. Version 2 remains the original proposal text.

## Product contract

### Version 1

- **Authentication:** `POST /auth/otp/request` accepts an email, normalizes it, creates the user if absent, invalidates earlier active challenges, and creates a random six-digit OTP. The OTP expires after 5 minutes, is single-use, and locks after 5 failed attempts. Only when `APP_ENV=development` and `ENABLE_DEMO_OTP=true`, the response includes the OTP for the UI to display; otherwise the field is omitted. `POST /auth/otp/verify` consumes the email/code pair and returns an HS256 Bearer JWT containing `sub`, `jti`, and `exp`. `GET /health/authenticated` validates a restored token during the auth bootstrap phase.

- **Server-side logout:** each successful login creates an auth-session record keyed by `jti`. Protected requests validate both the JWT and the active session, then reload the user. `POST /auth/logout` returns `204 No Content`, revokes only the current session, and the UI removes its token. Password registration, `passlib`, and password hashing are removed.

- **Admin access:** the Admin page is independent of user login and is available only in development (`APP_ENV=development` on the API; `import.meta.env.DEV` on the frontend). The operator enters the development-only `X-Admin-Key` value configured as `ADMIN_API_KEY`; every `/admin/*` request sends it. This is API-key authorization, not a user role.

- **Assets and balances:** balances are collections keyed by asset from the `currencies` catalog, initially `USDT` and `USD`, for both users and the singleton application/admin account. Amounts use Python `Decimal` and PostgreSQL fixed-precision `NUMERIC`, never floating point. USDT accepts up to 8 decimals and USD up to 4; an exchange amount must be exactly representable in the destination asset, so no implicit rounding occurs.

- **Deposits:** `POST /admin/deposits` takes user email, asset, and positive amount. In version 1 it immediately creates the user's missing balance row if needed and credits it. This mints demo funds and does not debit the admin balance.

- **Exchange:** `POST /me/exchanges` takes source asset, destination asset, and amount. Assets must differ, both must be supported, the source balance must be sufficient, and the fixed rate is 1:1. The two user balances change atomically.

- **Withdrawal:** `POST /me/withdrawals` takes asset and amount, debits the user's available balance, and credits the matching admin balance atomically.

- **Transfer:** `POST /me/transfers` takes recipient email, asset, and amount. The API resolves the recipient by normalized email, rejects self-transfers (`TRANSFER_TO_SELF`), validates same-currency 1:1 movement and sufficient funds, creates the recipient's missing balance row if needed, then atomically debits the sender and credits the recipient.

- **Queries:** users can retrieve their balance list and offset-paginated transaction history (`page_number`, `page_size`, `total_items`). Admin can retrieve the application balance list and offset-paginated transactions across all users. Read-only reference catalogs expose supported currencies (`GET /reference/currencies`) and registered users (`GET /reference/users`); both accept either `X-Admin-Key` or a user Bearer token.

- **History:** one immutable business transaction is recorded per deposit, exchange, withdrawal, or transfer. An exchange record contains both source and destination asset/amount. A transfer records the same asset on both sides at 1:1; user history may include a `direction` (`IN` or `OUT`) on transfer rows. Transaction rows carry IDs, owner, type, status, timestamps, and relevant asset/amount fields; balances and history are committed in one database transaction.

- **Safety rules:** amounts must be positive and within precision/range limits; insufficient funds are domain errors. Version 1 transactions complete synchronously. Balance-changing operations lock affected rows in a deterministic order inside one PostgreSQL transaction to prevent concurrent overspending and deadlocks.

### Version 2

- **All mutations become Kafka commands:** deposit, exchange, and withdrawal HTTP endpoints persist a `PENDING` business transaction plus an outbox message and return `202 Accepted` with the operation ID. The API does not synchronously execute or pre-validate current funds. A single command topic is partitioned by user ID so one user's commands retain order; one worker process dispatches to deposit, exchange, and withdrawal handlers, with asset-specific USDT/USD handling where needed.

- **Deposit:** request acceptance immediately adds the amount to the user's `pending` bucket. The Admin form includes an approve/reject checkbox whose selected mock decision travels in the command. The worker applies it: approval moves the amount `pending → available`; rejection moves it `pending → rejected`.

- **Exchange:** the worker validates distinct/supported assets, exact destination precision, and sufficient `available` source funds, then applies the 1:1 debit/credit atomically. Failure leaves balances unchanged and marks the transaction `REJECTED` with a safe reason.

- **Withdrawal:** the command identifies asset, amount, and source bucket (`available` or `rejected`). The worker validates funds, debits that user bucket, and credits the matching admin balance. `pending` funds cannot be withdrawn; rejected funds cannot be exchanged.

- **Results and reliability:** every worker outcome records `COMPLETED` or `REJECTED`, timestamps, and an optional safe result/error payload. Event IDs, operation IDs, inbox/outbox uniqueness, and state-transition checks make retries idempotent. The UI polls operation/history/balance queries while work is pending.

- **Kafka diagnostics page:** public React route `/kafka/` and unauthenticated read-only API endpoints expose paginated message records with correlation/operation ID, message/command type, state (`PENDING`, `PUBLISHED`, `PROCESSING`, `COMPLETED`, `REJECTED`, `FAILED`), timestamps, input payload, and result/error payload. Kafka is not queried as historical storage; producers and consumers maintain a PostgreSQL message log.

- **Removable boundary:** all diagnostics HTTP concerns live under a self-contained `app/kafka_api/` package (router, schemas/DTOs, query service, and read repository). Core wallet handlers do not import it. It reads the infrastructure message log through its own query boundary, is registered once in app composition, and can later be removed without changing wallet domain behavior. Payloads must exclude JWTs, OTPs, admin keys, and other secrets.

- WebSockets, real AML integrations, event sourcing, and distributed workflow orchestration remain out of scope.

## Domain and adapter shape

- Keep the framework-free hexagonal rule in [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md) and make CQRS explicit. `domain/use_cases/` is nested by concern (`otp/`, `wallet/`, `admin/`, `user/`, …) with `*_cmd.py` command handlers and `*_query.py` query handlers returning frozen, purpose-specific read models from `domain/read_models/`. Command repository ports and query/read ports are separate even though both adapters use the same PostgreSQL database. CQRS here does not mean event sourcing or separate databases.

- Expand domain concepts to `User`, `OtpChallenge`, `AuthSession`, `Money`, wallet balances, `Transaction`, asset/balance-bucket/transaction-status enums, and version-2 message/outbox state. Keep API, ORM, and domain models separate. API schemas validate shape and precision; command handlers enforce authorization, funds, and transitions; read models enforce local invariants at the persistence boundary; query handlers never mutate.

- Use PostgreSQL from version 1, with SQLAlchemy async through `asyncpg`, Alembic migrations under `backend/`, and PostgreSQL in Docker Compose. Integration tests use isolated PostgreSQL instances through `testcontainers`; no SQLite compatibility layer or alternate persistence profile is maintained. Version 1 automated tests are scaffolded under `backend/tests/` but the full unit/integration suite remains deferred to Phase 7.

- Extend the project tree with `backend/app/` (API, domain, auth, db adapters) and `frontend/` (Vite, React, TypeScript, native `fetch`, plain CSS). Version 2 adds `app/kafka_api/` and one Kafka command worker with separate handlers. The UI has Login, Wallet (embedded history), Admin, and version-2 Kafka Diagnostics views; view switching uses React state in version 1 (`react-router-dom` is installed but not wired). JWT and admin key are retained in `sessionStorage` for this demo and attached by a small API client. HTTP routes delegate through thin `api/executors/` wrappers into domain handlers.

- Version 1 Docker Compose starts PostgreSQL. Version 2 adds the Kafka broker and worker process. When implemented, unit tests cover entities and command/query handlers with fakes; integration tests cover PostgreSQL/HTTP, auth revocation, row-locking and concurrent-debit safety, async command outcomes, message ordering/idempotency, and the diagnostics API; minimal UI tests cover principal flows.

## Documentation changes

- [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md) retains PostgreSQL, `asyncpg`, and `testcontainers`; replaces password auth and client-only logout; and defines React, explicit hexagonal CQRS boundaries, fixed-precision money persistence, wallet/admin domain rules, API contracts, version-2 asynchronous command semantics, Kafka diagnostics isolation, testing boundaries, and explicit non-goals.

- [IMPLEMENTATION_STEPS.md](../IMPLEMENTATION_STEPS.md) is split into two executable phases. Version 1 covers PostgreSQL/backend/frontend scaffold, money/auth domain, command/query ports and handlers, persistence, OTP/JWT, HTTP composition, React UI, and verification. Version 2 adds balance buckets, operation/message migrations, outbox/contracts, Kafka, the command worker, three asynchronous command flows, isolated `/kafka/` diagnostics, UI polling/status handling, and ordering/idempotency/failure tests.

- The original request was removed after its intent was incorporated into the canonical documentation. The developer writes production code while AI supplies planning, explanation, review, and diagnosis when requested.
