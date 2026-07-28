# Implementation Steps

Work from top to bottom. Complete and understand version 1 before introducing Kafka. Each step states what to build and what proves it is complete.

The developer writes production code. AI can discuss design, review a proposed implementation, diagnose failures, and review completed changes when requested.

Human-directed phase guides may combine parts of several steps to support an implementation experiment.

## Version 1 — synchronous wallet

## Step 1 — Scaffold backend, frontend, and PostgreSQL

Runnable commands: [Phase 1 — Scaffolding](implementation/PHASE_1_SCAFFOLDING.md).

All Python/backend paths below are relative to `backend/`.

- [ ] Initialize the Python project with `uv` and Python 3.14 under `backend/`.
- [ ] Add backend runtime dependencies using the bounded ranges in `TECHNICAL_REQUIREMENTS.md`: FastAPI, Uvicorn, Pydantic, `pydantic-settings`, SQLAlchemy 2.0, asyncpg, Alembic, PyJWT, and `email-validator`.
- [ ] Add backend development dependencies: ruff, mypy, pytest, pytest-asyncio, HTTPX, and testcontainers.
- [ ] Configure ruff and strict mypy for SQLAlchemy 2.x native typing in `backend/pyproject.toml`.
- [ ] Create the initial `backend/app/`, `backend/tests/unit/`, `backend/tests/integration/`, and `backend/scripts/` packages/directories.
- [ ] Create a Vite React TypeScript project under `frontend/`.
- [ ] Enable Yarn with `corepack enable`; add React Router, ESLint, Vitest, React Testing Library, and basic frontend lint/typecheck scripts through Yarn.
- [ ] Configure `frontend/.yarnrc.yml` with `nodeLinker: node-modules`, commit `frontend/yarn.lock`, and verify that `yarn install --immutable` installs the frontend package tree in `frontend/node_modules`.
- [ ] Add `backend/.env.example`, a gitignored `backend/.env`, and `backend/app/config.py`.
- [ ] Add Docker Compose with one PostgreSQL service, persistent volume, health check, and exposed development port.
- [ ] Implement the profile and environment-variable contract in `CONFIGURATION.md`; create safe `.env.example` placeholders only.
- [ ] Add `/health/live` and `/health/ready` to the minimal FastAPI app.
- [ ] Create a minimal FastAPI app factory and a minimal React shell solely to prove both development servers start.

**Done when:** PostgreSQL becomes healthy, the backend and frontend hot-reload, health endpoints report correctly, `yarn install --immutable` installs packages under `frontend/node_modules`, ruff/mypy/frontend typecheck pass on the scaffold, and the backend can open and close an async PostgreSQL connection.

## Step 2 — Establish domain conventions and CQRS boundaries

- [ ] Create framework-free domain packages for entities, value objects, enums, the generic `Result[T]`, ports, command handlers, query handlers, and read models.
- [ ] Implement `Asset` with initial values `USDT` and `USD`.
- [ ] Implement a `Money` value object using `Decimal`.
- [ ] Enforce positive command amounts, non-negative stored balances, USDT scale 8, USD scale 2, and no implicit rounding.
- [ ] Define stable error-code constants for invalid amount, unsupported asset, invalid precision, and invalid state.
- [ ] Define the CQRS convention:
      - command DTO plus one async command handler returning `Result[T]`;
      - query DTO plus one async query handler returning `Result[T]` containing a frozen read model;
      - separate command-repository and query-repository Protocols.
- [ ] Implement immutable `Result[T]` with validated `success(data=None)` and `failure(error_code, reason=None)` factories and read-only `is_success`, `data`, `error_code`, and `reason` properties.
- [ ] Return failed results for expected outcomes; allow unexpected exceptions to propagate.
- [ ] Do not add a mediator or generic command bus; handlers are wired manually.
- [ ] Unit-test all money and precision behavior, including an amount that cannot be represented by the destination asset.

**Done when:** domain unit tests run with no imports from FastAPI, Pydantic, SQLAlchemy, PyJWT, or Kafka, and the command/query dependency direction can be explained from the code.

## Step 3 — Model user and OTP authentication

- [ ] Add the `User`, `OtpChallenge`, and `AuthSession` domain entities.
- [ ] Add frozen `CurrentUser` with user ID, normalized email, and current authentication-session `jti`.
- [ ] Define `CurrentUserProvider.get() -> CurrentUser` as a domain port; domain code reads it but never sets request context.
- [ ] Define OTP lifecycle behavior: 6 digits, 5-minute expiry, single use, invalidation by a newer challenge, and lock after 5 failed attempts.
- [ ] Define stable error codes for invalid, expired, locked, consumed, and superseded OTPs plus authentication failure.
- [ ] Define command repository ports for users, OTP challenges, and auth sessions.
- [ ] Define service ports for clock/time, OTP generation/digest, and JWT encode/decode where abstraction improves deterministic testing.
- [ ] Keep concrete OTP and PyJWT adapters outside `domain/`; command/query handlers import only the service Protocols.
- [ ] Unit-test OTP and auth-session transitions using a controllable fake clock.

**Done when:** authentication lifecycle rules are fully demonstrated by pure unit tests without HTTP, JWT, or database adapters.

## Step 4 — Model accounts, balances, and transactions

- [ ] Add a user wallet account and singleton admin account model.
- [ ] Add `Balance`, initially with the `AVAILABLE` bucket only.
- [ ] Add `DEPOSIT`, `EXCHANGE`, and `WITHDRAWAL` transaction types.
- [ ] Add version-1 `COMPLETED` transaction behavior and immutable financial terms.
- [ ] Define command repository methods needed to lock/create balances and persist business transactions.
- [ ] Define query ports and frozen read models for:
      - current-user balances;
      - admin balances;
      - user transaction history;
      - admin all-user transaction history.
- [ ] Define pagination input and stable ordering, newest transaction first with a deterministic tie-breaker.
- [ ] Unit-test balance debit/credit, insufficient funds, same-asset exchange, and transaction invariants.

**Done when:** all wallet rules can be exercised with plain domain objects and the read models contain only fields required by their query.

## Step 5 — Build the PostgreSQL persistence adapter

- [ ] Create the async SQLAlchemy engine and sessionmaker from settings.
- [ ] Implement the session lifecycle with `AsyncSession.begin()`: commit whenever a handler returns a `Result`, roll back when an unexpected exception escapes, and close always.
- [ ] Add SQLAlchemy models for users, accounts, balances, transactions, OTP challenges, and authentication sessions.
- [ ] Store money in PostgreSQL fixed-precision `NUMERIC`, with application and database constraints appropriate to asset precision and non-negative balances.
- [ ] Add unique constraints for account ownership, account/asset/bucket balances, OTP/session identity, and other domain uniqueness rules, including at most one current unconsumed/uninvalidated OTP challenge per user.
- [ ] Seed or deterministically create the singleton admin account.
- [ ] Implement domain/ORM mappers under `app/db/`.
- [ ] Implement command repositories, including deterministic `SELECT ... FOR UPDATE` balance locking.
- [ ] Implement query repositories as direct projections to frozen read models, with pagination.
- [ ] Initialize Alembic under `backend/`, connect metadata/settings, generate the initial migration, review it manually, and apply it.
- [ ] Add repository integration tests using PostgreSQL from testcontainers.

**Done when:** a clean test database can be migrated from zero, repositories round-trip domain values without precision loss, and query repositories issue purpose-specific projections.

## Step 6 — Build OTP and JWT adapters

- [ ] Implement cryptographically secure six-digit OTP generation.
- [ ] Implement a keyed OTP digest so codes are not persisted in plain text.
- [ ] Implement PyJWT HS256 encode/decode with `sub`, `jti`, and `exp`.
- [ ] Translate PyJWT decode and claim failures into `Result.failure("AUTHENTICATION_FAILED", reason=...)` without exposing adapter exceptions.
- [ ] Unit-test OTP format/digest behavior and JWT round trips, expiry, tampering, and invalid claims.
- [ ] Ensure OTPs, JWTs, admin keys, and secrets are excluded from normal logs.

**Done when:** adapters satisfy their Protocols and pass isolated unit tests without FastAPI or PostgreSQL.

## Step 7 — Implement authentication commands and current-user query

- [ ] Implement the request-OTP command:
      - normalize email;
      - atomically create the user if absent and lock that user before challenge changes;
      - invalidate prior challenges;
      - persist a new challenge;
      - return the demo OTP and expiry.
- [ ] Implement the verify-OTP command:
      - load the current and digest-matching challenges under the user lock;
      - distinguish invalid, expired, locked, consumed, and superseded challenges;
      - count failed attempts and return the expected failed `Result`, allowing normal transaction exit to commit the count;
      - consume a valid challenge;
      - create an auth session;
      - return the Bearer JWT.
- [ ] Inject repository Protocols directly into handlers; keep SQLAlchemy sessions and transaction management outside `domain/` and do not add a custom Unit of Work.
- [ ] Implement logout so its handler obtains `CurrentUser` through an injected `CurrentUserProvider` and revokes that session's `jti`; do not copy the principal into `LogoutCommand`.
- [ ] Implement current-user loading that validates token, active auth session, and fresh user state.
- [ ] Unit-test each command handler using fake repositories, services, and current-user providers, including every failure branch and multiple independent sessions.

**Done when:** command-handler tests prove that OTPs are single-use and logout revokes only the current session.

## Step 8 — Implement synchronous wallet commands and queries

- [ ] Return `Result[T]` from every wallet command and query; represent expected validation, authorization, not-found, conflict, and insufficient-funds outcomes with stable failed-result error codes.
- [ ] Inject `CurrentUserProvider` into authenticated HTTP wallet handlers instead of repeating `current_user` fields in their command/query DTOs; keep admin and worker identity explicit to their own inputs.
- [ ] Implement admin mock deposit:
      - find the target by normalized email;
      - create/lock the user's balance;
      - credit available funds;
      - add a completed deposit transaction;
      - do not debit admin.
- [ ] Implement exchange:
      - require different supported assets;
      - require exact destination precision;
      - lock both balances in deterministic order;
      - verify source funds;
      - debit/credit at 1:1;
      - add one completed exchange transaction with both sides.
- [ ] Implement withdrawal:
      - lock user and admin balances in deterministic order;
      - validate available funds;
      - debit user and credit admin;
      - add one completed withdrawal transaction.
- [ ] Implement balance and transaction query handlers for users and admin.
- [ ] Unit-test command and query handlers with fake repositories, asserting `is_success`, `data`, and `error_code`.
- [ ] Integration-test each handler with real PostgreSQL transactions.
- [ ] Add a concurrent-withdrawal/exchange test proving the same balance cannot be overspent.

**Done when:** every mutation changes balances and writes history atomically, and concurrent debit attempts leave no negative balance.

## Step 9 — Build and compose the HTTP API

- [ ] Add Pydantic request/response schemas for auth, wallet, admin, balances, transactions, errors, and pagination.
- [ ] Implement the request, response, HTTP-status, error-envelope, and cursor-pagination contracts in `API_CONTRACT.md`.
- [ ] Keep DTO-to-command and read-model-to-response mapping in `app/api/`.
- [ ] Add `api/result_mapping.py` with generic `unwrap_result(Result[T]) -> T`; return successful data and raise an API-layer result exception carrying only `error_code` for failure, using `T = None` for no-content commands.
- [ ] Add one central mapping from the API-layer result exception to HTTP status and safe error envelopes; treat unmapped codes and unexpected exceptions as `500 INTERNAL_ERROR`.
- [ ] Keep successful status codes route-specific and keep request validation as `422 VALIDATION_ERROR`; never derive either from `unwrap_result`.
- [ ] Never expose or automatically log `Result.reason` through the API layer.
- [ ] Implement the domain `CurrentUserProvider` port in `api/current_user_provider.py` with request-scoped `ContextVar` storage and adapter-only bind/reset operations.
- [ ] Authenticate each protected request once, bind the validated `CurrentUser`, and reset the exact context token in `finally`; use the same provider instance for binding and protected-handler injection.
- [ ] Treat provider access without a bound user as an unexpected wiring error, and do not use the HTTP current-user provider in admin or Kafka worker execution paths.
- [ ] Add composition providers for settings, sessions, repositories, services, command handlers, and query handlers.
- [ ] Use `HTTPBearer(auto_error=False)` for protected user routes and Swagger Bearer authorization support; map missing credentials to the standard 401 envelope.
- [ ] Add timing-safe `X-Admin-Key` validation for `/admin/*`; do not require user JWT there.
- [ ] Add version-1 routes:
      - `POST /auth/otp/request`;
      - `POST /auth/otp/verify`;
      - `POST /auth/logout`;
      - `GET /health/authenticated`;
      - `GET /me/balances`;
      - `POST /me/exchanges`;
      - `POST /me/withdrawals`;
      - `GET /me/transactions`;
      - `POST /admin/deposits`;
      - `GET /admin/balances`;
      - `GET /admin/transactions`.
- [ ] Add `GET /health/live` and `GET /health/ready`.
- [ ] Register routers and exception handlers in the app factory.

**Done when:** routers only translate HTTP to/from handlers, `unwrap_result` preserves successful payloads and maps every documented failure code to the correct status/envelope, malformed DTOs produce 422, unknown codes produce a safe 500, authenticated request context is reset without cross-request leakage, health endpoints report accurately, and Swagger can exercise all version-1 flows.

## Step 10 — Build the version-1 React UI

- [ ] Create a typed API client with separate JWT and admin-header helpers.
- [ ] Store the JWT and demo admin key in `sessionStorage` only in the development profile.
- [ ] Build Login:
      - request OTP;
      - display the demo OTP;
      - submit email/code;
      - navigate to Wallet after success.
- [ ] Build Wallet:
      - list USDT/USD balances;
      - exchange in either direction;
      - withdraw either asset;
      - show immediate completed results and errors;
      - log out.
- [ ] Build History with pagination.
- [ ] Build the development-only Admin page without requiring user login:
      - capture the admin key;
      - create USDT/USD deposits;
      - show admin balances;
      - show all-user transaction history.
- [ ] Keep styling deliberately simple and accessible.
- [ ] Add minimal tests for login, auth-header attachment, admin-header attachment, and one wallet command.

**Done when:** a browser can complete the entire version-1 scenario without Swagger, production configuration omits demo-only routes/features, and frontend typecheck/tests pass.

## Step 11 — Complete version-1 integration coverage

- [ ] Run Alembic migrations in each testcontainers PostgreSQL instance.
- [ ] Cover OTP request and first-time user registration.
- [ ] Cover invalid, expired, locked, and reused OTPs through their failed-result error codes; prove a wrong-attempt increment persists despite the error response.
- [ ] Cover protected routes and server-side logout revocation.
- [ ] Cover request-scoped current-user binding/reset and prove one request's principal cannot leak into another request or a background execution path.
- [ ] Cover admin-key rejection and success.
- [ ] Cover USDT scale 8, USD scale 2, and non-representable exchanges.
- [ ] Cover deposit, both exchange directions, both withdrawal assets, admin balances, and user/admin history.
- [ ] Cover automatic transaction commit for returned results, rollback when an unexpected exception escapes, and concurrent balance safety.
- [ ] Run ruff, mypy, unit tests, integration tests, frontend tests, and frontend production build.

**Done when:** version 1 is reproducible from a fresh clone and all checks pass. Tag or otherwise mark this point before starting version 2.

## Version 2 — Kafka-executed commands

## Step 12 — Evolve balance and operation persistence

- [ ] Add `PENDING` and `REJECTED` user balance buckets.
- [ ] Add transaction statuses `PENDING`, `REJECTED`, and `FAILED` while retaining `COMPLETED`.
- [ ] Add safe failure/result fields and lifecycle timestamps.
- [ ] Add outbox, inbox/processed-message, and Kafka diagnostics message persistence.
- [ ] Add unique message/operation constraints preventing duplicate application.
- [ ] Write and manually review an Alembic migration.
- [ ] Update domain transitions, repositories, read models, and unit tests.

**Done when:** existing version-1 data migrates safely and repository tests cover every new bucket/status transition.

## Step 13 — Define Kafka contracts and infrastructure

- [ ] Define a versioned command envelope with message ID, operation ID, command type, user partition key, correlation/causation IDs, timestamp, and typed payload.
- [ ] Define deposit, exchange, and withdrawal payloads independent of API DTOs and ORM models.
- [ ] Add the pinned Kafka broker and worker services/configuration to Docker Compose.
- [ ] Implement the `aiokafka` producer/consumer adapter behind messaging ports.
- [ ] Implement an outbox relay that safely claims and publishes rows.
- [ ] Record publication attempts, broker metadata, timestamps, and failures.
- [ ] Use target user ID as the message key, `wallet.commands.v1` as the command topic, and `wallet-command-worker-v1` as the consumer group.
- [ ] Document at-least-once delivery explicitly.

**Done when:** a test command can move from PostgreSQL outbox to Kafka and its published state is observable without invoking wallet business behavior.

## Step 14 — Implement asynchronous command submission

- [ ] Replace version-2 deposit, exchange, and withdrawal HTTP behavior with submission handlers that return an operation ID.
- [ ] Persist the pending transaction and outbox command atomically.
- [ ] For deposit only, increment the pending balance in that transaction.
- [ ] Add the Admin approval checkbox value to the deposit command payload.
- [ ] Do not reserve exchange or withdrawal funds at submission.
- [ ] Return `202 Accepted` from all three command endpoints.
- [ ] Add user/admin operation-status queries with ownership/access checks.
- [ ] Test rollback so no pending operation can exist without its outbox row and vice versa.

**Done when:** HTTP submission never directly executes exchange/withdrawal and every accepted operation is discoverable as pending.

## Step 15 — Implement the command worker

- [ ] Create one consumer group and one worker entry point.
- [ ] Add dispatch to deposit, exchange, and withdrawal execution handlers.
- [ ] Record inbox/processing state before execution.
- [ ] Deposit:
      - checked approval moves `pending → available`;
      - unchecked approval moves `pending → rejected`.
- [ ] Exchange:
      - validate current available source funds and precision in the worker;
      - atomically update available source/destination;
      - otherwise reject without balance changes.
- [ ] Withdrawal:
      - validate the requested `available` or `rejected` source bucket;
      - atomically debit user and credit admin;
      - reject pending-bucket requests.
- [ ] Mark business outcomes `COMPLETED` or `REJECTED`.
- [ ] Map expected worker-handler `Result.failure(error_code)` outcomes to `REJECTED` with a safe reason code.
- [ ] Let unexpected exceptions escape the handler, then mark their operations `FAILED` and keep them retryable.
- [ ] Make duplicate delivery return the stored outcome without applying money twice.
- [ ] Preserve per-user command order through Kafka keying and consumer design.

**Done when:** all three commands execute only after Kafka consumption and duplicate messages cannot duplicate any financial effect.

## Step 16 — Build the isolated Kafka diagnostics API

- [ ] Create `app/kafka_api/` with its own router, schemas/DTOs, query service, and read repository.
- [ ] Keep wallet domain and command handlers free of imports from this package.
- [ ] Query PostgreSQL message records rather than attempting to query Kafka history.
- [ ] Add development-profile-only, unauthenticated, read-only endpoints:
      - `GET /kafka/messages`;
      - `GET /kafka/messages/{message_id}`.
- [ ] Support pagination and useful filters such as state, command type, operation ID, and correlation ID.
- [ ] Return input, result/error, broker metadata, and lifecycle timestamps.
- [ ] Sanitize OTPs, JWTs, admin keys, secrets, and connection values before persistence and response.
- [ ] Register this router once in `main.py` so removing registration/package does not change wallet behavior.

**Done when:** the module can be removed from application composition without modifying domain/use-case code and API tests prove that secret fields cannot appear.

## Step 17 — Update the React UI for version 2

- [ ] Update wallet/admin mutations to handle `202 Accepted`.
- [ ] Show pending operation IDs and poll operation status.
- [ ] Display `available`, `pending`, and `rejected` balances per asset.
- [ ] Add Admin's approve/reject checkbox to the deposit form.
- [ ] Let withdrawal select `available` or `rejected`; never offer `pending`.
- [ ] Render completed, rejected, and failed outcomes with safe reasons.
- [ ] Add development-only `/kafka/` route with message list, filters, details, states, timestamps, input, and result/error.
- [ ] Poll diagnostics with the bounded exponential-backoff settings in `CONFIGURATION.md` rather than adding WebSockets.
- [ ] Add focused tests for async status rendering and Kafka diagnostics.

**Done when:** all version-2 states can be demonstrated in the browser, including approved/rejected deposits and worker-rejected exchange/withdrawal.

## Step 18 — Complete version-2 reliability tests

- [ ] Cover outbox retry after broker unavailability.
- [ ] Cover duplicate publication and duplicate consumption.
- [ ] Cover ordered commands for one user.
- [ ] Cover independent processing for different users.
- [ ] Cover an exchange/withdrawal accepted by HTTP but later rejected for insufficient funds.
- [ ] Cover approved and rejected deposits and withdrawals from rejected funds.
- [ ] Cover raised infrastructure exceptions becoming `FAILED` separately from failed `Result` business outcomes becoming `REJECTED`.
- [ ] Cover worker restart and recovery of unfinished messages.
- [ ] Cover Kafka diagnostics filtering, timestamps, payloads, and sanitization.
- [ ] Run all backend/frontend quality checks and verify the startup, demo, release, rollback, backup, and incident procedures in `README.md` and `OPERATIONS.md`.

**Done when:** version 2 demonstrates asynchronous execution, at-least-once delivery, duplicate-message safety, ordering, and observability without claiming production exactly-once guarantees.

## Required completion controls

- [ ] Add pre-commit checks for ruff, mypy, and fast unit tests.
- [ ] Add CI for backend lint/typecheck/tests, frontend typecheck/tests/build, PostgreSQL integration tests, and version-2 Kafka integration tests.
- [ ] Add dependency vulnerability scanning and a recurring dependency-review process.
- [ ] Add architecture decision records for CQRS, generic `Result[T]` plus automatic transaction contexts, PostgreSQL, OTP sessions, outbox/duplicate-message handling, and the removable Kafka diagnostics adapter.

## Optional final phase — HTTP request idempotency

Do not implement this phase unless it is explicitly requested. It is intentionally last and is not required for either baseline application version.

- [ ] Require an `Idempotency-Key` UUID only on the mutating routes selected for hardening.
- [ ] Persist the key with principal, method, route, canonical payload hash, original status, and original response.
- [ ] Replay the original result for an identical request and return `409 IDEMPOTENCY_KEY_REUSED` when the same key is reused with different request identity or content.
- [ ] Define retention and cleanup behavior.
- [ ] Add concurrency and replay tests before documenting the feature in the baseline API contract.

**Done when:** explicitly selected routes safely replay identical requests without repeating their effects, conflicting reuse is rejected, and no route outside this optional scope requires the header.
