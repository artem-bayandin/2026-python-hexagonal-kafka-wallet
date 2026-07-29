# Wallet Sample — Functional Requirements

## 1. Purpose

Build a small educational custodial-wallet web application in two versions. It uses a React UI and a Python API to demonstrate OTP authentication, USDT/USD balances, mocked deposits, 1:1 exchange, withdrawals, transaction history, Clean/Hexagonal Architecture, CQRS, and asynchronous Kafka processing.

The application is a learning sample. It does not move real money, send real email, perform real AML checks, or provide production-grade administration. [README.md](README.md) defines this document's authority and the version-specific reading order.

## 2. Actors

### 2.1 User

A user authenticates by email and OTP, views balances and transaction history, exchanges funds, withdraws funds, and logs out.

### 2.2 Admin operator

The admin operator is not a user role and does not need a user JWT. In development, the operator opens the Admin page, enters the demo-only `X-Admin-Key` configured as `ADMIN_API_KEY`, and the UI sends that header with every admin API request. This page is disabled outside development.

The admin can create mock deposits, view the application/admin balances, and view transactions across all users.

## 3. Assets and money rules

- The initial supported assets are `USDT` and `USD`.
- User and admin balances are collections keyed by asset, not hard-coded `crypto_balance` and `fiat_balance` fields.
- USDT supports at most 8 decimal places.
- USD supports at most 4 decimal places.
- Amounts must be positive and are never represented using binary floating point.
- The sample exchange rate is fixed at `1 USDT = 1 USD`.
- Source and destination assets must differ.
- An exchange is rejected if its amount cannot be represented exactly using the destination asset's precision. No implicit rounding is allowed.

## 4. Authentication

### 4.1 Request OTP

1. The user enters an email.
2. The API normalizes the email and creates the user if it does not exist.
3. The API invalidates earlier active OTP challenges for that email.
4. The API creates a random six-digit OTP.
5. The OTP expires after 5 minutes, is single-use, and locks after 5 failed verification attempts.
6. Only in development, with the explicit demo-OTP flag enabled, the API returns the OTP in the response and the UI displays it so the user can copy it.

No password is collected or stored, and no real email is sent.

### 4.2 Verify OTP

1. The user submits the email and OTP.
2. The API validates and consumes the challenge.
3. The API creates an authentication session and issues an HS256 Bearer JWT containing at least `sub`, `jti`, and `exp`.
4. The UI stores the token in `sessionStorage` and sends it in the `Authorization: Bearer` header on protected requests.

### 4.3 Logout

The logout endpoint revokes the authentication session identified by the current JWT's `jti`. The UI then removes its token. Logging out one session does not revoke the user's other sessions.

Protected requests validate the JWT, verify that its server-side session is still active, and load the current user from the database.

During the authentication-only phase, the index page uses `GET /health/authenticated` to validate a token restored from `sessionStorage`. It shows the login form without a valid token and a minimal **Authorized** state with logout when validation succeeds; the later Wallet page replaces this temporary authenticated state.

## 5. Version 1 — synchronous wallet

### 5.1 Mock deposit

The admin submits a user email, asset, and amount. The API creates any missing balance record and immediately credits the user's available balance.

A mock deposit creates demo funds. It does not debit the admin balance.

### 5.2 View balances

A user can view a list containing the current available balance for each supported asset. The admin can view the application/admin balance list.

### 5.3 Exchange

The user submits source asset, destination asset, and amount. The API validates asset support, precision, distinct assets, and sufficient source funds, then atomically debits the source balance and credits the destination balance at 1:1.

### 5.4 Withdraw

The user submits an asset and amount. The API atomically debits the user's available balance and credits the matching admin balance.

### 5.5 Transaction history

One business transaction is created for each deposit, exchange, or withdrawal. Its financial terms are immutable. An exchange transaction records both source and destination assets and amounts.

Users can view their own paginated history. Admin can view paginated history across all users. Version 1 transactions complete synchronously.

## 6. Version 2 — Kafka-executed wallet commands

### 6.1 General command lifecycle

Deposit, exchange, and withdrawal become asynchronous commands:

1. The HTTP endpoint creates a `PENDING` business transaction and an outbox message in one database transaction.
2. The endpoint returns `202 Accepted` with an operation ID.
3. An outbox relay publishes the command to Kafka.
4. Commands use the target user ID as the Kafka partition key so commands for one user retain order.
5. A single worker process consumes commands and dispatches them to deposit, exchange, or withdrawal handlers, with separate USDT/USD handling where required.
6. The worker performs current-state validation and marks the operation `COMPLETED` or `REJECTED`.

Exchange and withdrawal funds are not reserved by the HTTP API. Therefore an accepted command can later be rejected by the worker, for example because a previous queued command spent the available balance.

Message delivery is at least once. Event IDs, operation IDs, inbox/outbox uniqueness, and guarded state transitions make retries idempotent.

### 6.2 Balance buckets

Each user balance exposes:

- `available`: can be exchanged or withdrawn;
- `pending`: cannot be exchanged or withdrawn;
- `rejected`: cannot be exchanged, but can be withdrawn.

### 6.3 Deposit command

The Admin form includes an approval checkbox:

- checked means the mocked AML decision is approval;
- unchecked means the mocked AML decision is rejection.

When the API accepts the deposit, it immediately increments the user's pending bucket and writes the command to the outbox. The selected mock decision travels in the command but is not applied by the API.

The worker moves the amount:

- from `pending` to `available` when approved;
- from `pending` to `rejected` when rejected.

An unexpected infrastructure failure is recorded as `FAILED` and remains retryable; it is not treated as an AML rejection.

### 6.4 Exchange command

The worker validates the assets, precision, and current available source balance. On success it atomically debits the available source balance and credits the available destination balance. On business failure it changes no balance and marks the operation `REJECTED` with a safe reason.

### 6.5 Withdrawal command

The command identifies the asset, amount, and source bucket (`available` or `rejected`). The worker validates and debits that bucket, then credits the matching admin balance. Pending funds cannot be withdrawn.

## 7. Kafka diagnostics

Version 2 provides, only when the explicit development diagnostics flag is enabled:

- a public React route at `/kafka/`;
- unauthenticated, read-only Kafka diagnostics API endpoints;
- pagination and filtering for message records;
- message/command type, operation and correlation IDs;
- state such as `PENDING`, `PUBLISHED`, `PROCESSING`, `COMPLETED`, `REJECTED`, or `FAILED`;
- created, published, processing, and completion timestamps;
- sanitized input data and result/error data.

Kafka is not used as a queryable historical database. Producers and consumers maintain a PostgreSQL message log that powers this page.

All diagnostics HTTP code lives in a self-contained `app/kafka_api/` package with its own router, schemas/DTOs, query service, and read repository. Wallet domain handlers do not import it. It is registered once in application composition so it can later be removed without changing wallet behavior.

JWTs, OTPs, admin keys, and secrets must never be written to the diagnostics payload. This unauthenticated page is a development-only teaching tool, returns `404` when disabled, and must not be enabled unchanged in a real application.

## 8. UI pages

The Vite/React/TypeScript application uses plain CSS and native `fetch`.

- **Login:** request OTP, display the demo OTP only in development, verify it, and establish the session.
- **Wallet:** show balances, submit exchanges and withdrawals, show immediate results in version 1, show pending-operation feedback in version 2, and log out.
- **History:** show the current user's paginated transactions and statuses.
- **Admin:** development-only; capture the admin key, create deposits, choose the version-2 mock decision, and show admin balances and all transactions.
- **Kafka:** development-only version-2 message diagnostics without authentication.

The JWT and demo admin key are kept in `sessionStorage` only for the development sample. This is intentionally simple and is not the recommended production security model.

## 9. Explicit non-goals

- Real cryptocurrency, banking, custody, or payment integrations.
- Real email delivery or production OTP security.
- Real AML providers or compliance decisions.
- Market prices, fees, slippage, or assets beyond USDT and USD.
- Refresh tokens, cookie authentication, MFA, or password login.
- Event sourcing or separate CQRS read/write databases.
- WebSockets; the UI polls operation, balance, and history queries.
- Production exposure of the Admin or Kafka diagnostics pages.
- Deploying this sample before the required production controls are implemented and approved.
