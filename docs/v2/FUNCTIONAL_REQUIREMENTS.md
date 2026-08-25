# Wallet Sample — Version 2 Functional Requirements

## 1. Purpose and authority

Version 2 is the canonical product contract for a small custodial-wallet learning application. It uses a React UI and a Python API to demonstrate OTP authentication, USDT/USD balances, mock deposits, 1:1 exchanges, withdrawals, user-to-user transfers, transaction history, Clean/Hexagonal Architecture, CQRS, and asynchronous wallet-command processing through Kafka.

The application does not move real money and is not a production wallet. [README.md](README.md) is authoritative for Version 2 architecture decisions, while [the Version 1 functional requirements](../v1/FUNCTIONAL_REQUIREMENTS.md) remain the baseline for money, authentication, and other behavior that this contract does not change.

Version 1 executes wallet writes synchronously. Version 2 replaces execution of all four wallet operations with one asynchronous contract while preserving their financial meaning. Existing Version 1 transaction outcomes represented as `completed` migrate to the Version 2 terminal status `succeeded`; all new behavior and terminology in this document describe the Version 2 target state.

## 2. Actors

### 2.1 User

A user authenticates by email and OTP, views balances and personal transaction history, submits exchanges, withdrawals, and transfers, receives live status updates for those transactions, and logs out.

### 2.2 Admin operator

The admin operator is not a user role and does not use a user JWT. In development, the operator opens the Admin page, enters the demo-only `X-Admin-Key` configured as `ADMIN_API_KEY`, and the UI sends that header with every admin API request.

The admin can submit mock deposits, view application/admin balances, and observe transactions across all users through long polling. The Admin page is disabled outside development.

## 3. Assets and money baseline

- The supported assets are `USDT` and `USD`.
- User and admin balances are collections keyed by asset.
- USDT supports at most 8 decimal places.
- USD supports at most 4 decimal places.
- Every amount must be positive and must not use binary floating-point representation.
- The fixed sample exchange rate is `1 USDT = 1 USD`.
- Exchange source and destination assets must differ.
- An exchange amount must be exactly representable at the destination asset's precision; implicit rounding is not allowed.
- Financial changes for one command are atomic.

## 4. Authentication baseline

### 4.1 Request OTP

1. The user enters an email address.
2. The API normalizes the email and creates the user if the user does not exist.
3. The API invalidates earlier active OTP challenges for that email.
4. The API creates a random six-digit OTP.
5. The OTP expires after 5 minutes, is single-use, and locks after 5 failed verification attempts.
6. Only in development, and only when the explicit demo-OTP flag is enabled, the API returns the OTP and the UI displays it for copying.

No password is collected or stored, and no real email is sent.

### 4.2 Verify OTP

1. The user submits the normalized email and OTP.
2. The API validates and consumes the challenge.
3. The API creates an authentication session and issues an HS256 Bearer JWT containing at least `sub`, `jti`, and `exp`.
4. The UI stores the token in `sessionStorage` and sends it in the `Authorization: Bearer` header on protected requests.

### 4.3 Protected requests and logout

Protected requests validate the JWT, confirm that its server-side session remains active, and load the current user from the database.

Logout revokes the authentication session identified by the current JWT's `jti`, after which the UI removes its token. Logging out one session does not revoke the user's other sessions.

## 5. Shared asynchronous wallet contract

The four asynchronous wallet operations are admin deposit, user withdrawal, user exchange, and user transfer. Their submission endpoints are:

| Actor | Method | Path | Debit lock |
| --- | --- | --- | --- |
| Admin | `POST` | `/admin/deposits` | None |
| User | `POST` | `/me/withdrawals` | Source amount |
| User | `POST` | `/me/exchanges` | Source amount |
| User | `POST` | `/me/transfers` | Source amount |

### 5.1 Submission response and identity

An accepted submission returns `202 Accepted` with `{request_id}`. The `request_id` is a unique UUID generated for the business transaction and is the public identifier used consistently in submission responses, transaction history, status events, and UI reconciliation.

The `202 Accepted` response means that the command was recorded for asynchronous processing; it does not mean that the financial change has succeeded. The durable transaction record is the source of truth for its current status and outcome.

Submission performs request authentication, input-shape validation, asset and precision validation, and all checks required to establish a valid command. Invalid input, an unsupported asset, an impermissible exchange pair, an unrepresentable amount, a missing transfer recipient, a self-transfer, or insufficient spendable funds fails synchronously and creates no transaction.

### 5.2 Status lifecycle

Every accepted transaction uses only these lowercase statuses:

| Status | Meaning |
| --- | --- |
| `submitted` | The transaction exists; any required debit is locked; publication has not yet been acknowledged. |
| `pending` | Publication has been acknowledged and the transaction is waiting for worker execution. |
| `in_progress` | The worker is executing the transaction; internal retries retain this status. |
| `succeeded` | The financial change completed atomically and any debit lock was settled. |
| `failed` | The transaction reached a terminal failure; any debit lock was released and a safe error is available. |

The normal lifecycle is `submitted → pending → in_progress → succeeded|failed`. Status transitions are guarded and idempotent so at-least-once delivery or redelivery cannot apply the same financial change twice.

Consumers of status data must tolerate skipped observations. A transaction can advance faster than the UI receives each intermediate event, but its persisted status remains authoritative.

Transactions preserve submission order for commands associated with the same user. Admin deposits preserve their own submission order.

### 5.3 Submit-time debit locking

Withdrawal, exchange, and transfer lock the source amount in the same database transaction that creates the transaction in `submitted`. The lock succeeds only when `amount - locked` is at least the requested debit; otherwise submission fails synchronously with `409 INSUFFICIENT_FUNDS` and creates no transaction.

A successful debit command atomically subtracts the debit from both `amount` and `locked` while applying its credit-side effect. A failed debit command leaves `amount` unchanged and subtracts the reserved debit from `locked`.

A deposit is credit-only and never creates a lock.

### 5.4 Balance semantics

`GET /me/balances` returns `amount` and `locked` for every supported asset. `amount` is the wallet's total posted balance, `locked` is the portion reserved by accepted debit commands that have not reached a terminal status, and spendable funds equal `amount - locked`.

Submitting a debit command increases `locked` without immediately decreasing `amount`. On success, settlement decreases both values by the debit amount; on failure, release decreases only `locked`.

The UI displays `amount` and `locked` distinctly and may derive spendable funds as `amount - locked`. It must never present `amount` alone as immediately spendable when `locked` is nonzero.

## 6. Wallet operations

### 6.1 Admin deposit

The admin submits a target user email, asset, and amount. The API normalizes and resolves the target user, validates the asset and amount, creates any missing target balance record as needed, records the transaction, and returns `202 Accepted` with `{request_id}`.

The worker atomically credits the user's `amount` and marks the transaction `succeeded`. A mock deposit creates demo funds and does not debit an admin balance.

### 6.2 User withdrawal

The user submits an asset and amount. The API validates the request, locks the amount in the matching user wallet, records the transaction, and returns `202 Accepted` with `{request_id}`.

The worker atomically settles the user's lock by decreasing the user's `amount` and `locked`, credits the matching admin balance, and marks the transaction `succeeded`.

### 6.3 User exchange

The user submits source asset, destination asset, and amount. The API validates supported and distinct assets, source and destination precision, exact 1:1 representability, and sufficient spendable source funds; it then locks the source amount, records the transaction, and returns `202 Accepted` with `{request_id}`.

The worker atomically settles the source lock, decreases the source `amount`, credits the destination `amount` at 1:1, and marks the transaction `succeeded`.

### 6.4 User transfer

The user submits a recipient email, asset, and amount. The API normalizes and resolves the recipient, disallows self-transfer, validates same-asset 1:1 movement and sufficient spendable source funds, locks the sender's source amount, records the resolved recipient with the transaction, and returns `202 Accepted` with `{request_id}`.

The worker revalidates the recipient, then atomically settles the sender's lock, decreases the sender's `amount`, credits the recipient's matching `amount`, and marks the transaction `succeeded`.

## 7. Transaction history

One business transaction is created for each accepted deposit, withdrawal, exchange, or transfer. Its financial terms are immutable after submission. An exchange records both source and destination assets and amounts; a transfer records the same asset on both sides at 1:1.

`GET /me/transactions` returns paginated history involving the authenticated user's wallets and includes `request_id`, type, immutable financial terms, status, timestamps, and a safe nullable `error`. This includes both outgoing and incoming transfers, distinguished by direction; transactions unrelated to the user remain inaccessible.

`GET /admin/transactions` returns transactions across all users with the same lifecycle information. A transaction appears from its creation in `submitted`, and later status changes update the same transaction rather than creating separate business transactions.

History and live updates are two views of the same persisted transaction state. Reloading the UI or missing a live event must not lose the ability to determine the current outcome.

## 8. User live status with SSE

`GET /me/stream` is an authenticated Server-Sent Events stream for status changes visible through the current user's transaction-history query, including incoming transfers. Each event contains `{request_id, status, error?}` and reflects a persisted transition of a transaction involving the user's wallets.

The client reconnects when the stream is interrupted. After reconnecting, transaction history remains the recovery source of truth, so duplicate events, delayed events, or a missed intermediate status cannot produce a false final state.

The Wallet UI reconciles events by `request_id`, updates the matching history row and status indicator, and tolerates transitions that appear to skip intermediate statuses. On `succeeded`, it refetches balances and relevant transaction history. On `failed`, it removes any temporary submission indicator, refetches authoritative data, and displays the safe error.

The SSE stream is one-way from server to client. Wallet command submission continues to use authenticated HTTP requests.

## 9. Admin long polling

The Admin UI observes transaction creation and status changes by repeatedly long-polling `GET /admin/transactions`. The endpoint reads the database and uses a keyset cursor over `(updated_at, id)`, represented directly or as one opaque cursor.

Each request asks for rows after the previous cursor in ascending `(updated_at, id)` order. A newly submitted transaction and every later status change advance `updated_at`, so the same transaction can appear in multiple responses.

The Admin UI upserts returned rows by transaction identity and `request_id`; it must not append duplicate rows for repeated updates. It advances its cursor only through the ordered response it has processed, immediately issues the next long-poll request after a response or timeout, and retries transient failures with bounded backoff.

Long polling must make a transaction visible from creation and preserve later transitions even when processing is slow. A UUID by itself is not a chronological cursor and must not be used as one.

## 10. Failure behavior

Submission failures that occur before a transaction is accepted return the appropriate HTTP error, create no transaction, and create no lock. This includes authentication and authorization failures, malformed input, unsupported money terms, missing or invalid transfer recipients, self-transfer, and insufficient spendable funds.

If publication cannot be acknowledged after bounded producer retries, the accepted transaction becomes `failed`, any debit lock is released, and a safe error is persisted. Accepted transactions must not remain indefinitely in `submitted`; stale `submitted` transactions are republished by a recovery process.

The worker retries retryable execution failures up to three times with backoff while the transaction remains `in_progress`. If all attempts fail, the worker marks the transaction `failed`, releases any debit lock, persists a safe error, and isolates the failed command so it cannot block subsequent work.

Stale `pending` or `in_progress` transactions indicate consumer lag or worker failure and require operational alerting or manual recovery; they are not blindly resubmitted. Duplicate delivery is safe because guarded transitions and atomic wallet mutations ensure that a terminal transaction cannot apply twice.

Any failure after acceptance is represented by terminal status `failed`, not by a separate business-outcome status. Errors exposed through history, SSE, or admin polling must be safe for display and must not contain JWTs, OTPs, admin keys, secrets, or internal stack traces.

## 11. UI pages

The Vite/React/TypeScript application uses plain CSS and native `fetch`.

- **Login:** request an OTP, display the demo OTP only in development when enabled, verify it, establish the session, and restore or clear the session based on authenticated validation.
- **Wallet:** display `amount`, `locked`, and derived spendable balances; show paginated transaction history and lifecycle indicators; submit exchanges, withdrawals, and transfers; consume SSE status events; refetch balances on success; show safe failure errors; and log out.
- **Admin:** development-only; capture the admin key, submit mock deposits, display admin balances, and long-poll all transactions while upserting lifecycle changes.

The JWT and demo admin key are stored in `sessionStorage` only for this development sample. This is intentionally simple and is not a recommended production security model.

## 12. Explicit non-goals

- Real cryptocurrency, banking, custody, payment, or settlement integrations.
- Real email delivery or production OTP security.
- Real AML providers, compliance decisions, or deposit approval workflows.
- Market prices, fees, slippage, implicit rounding, or assets beyond USDT and USD.
- Refresh tokens, cookie authentication, MFA, or password login.
- Production-grade admin authentication or production exposure of the Admin page.
- Exactly-once end-to-end delivery; Version 2 uses at-least-once delivery with database idempotency.
- WebSockets or bidirectional real-time transport.
- Event sourcing or separate CQRS read/write databases.
- Persisted cross-delivery retry counters.
- End-user replay or infrastructure-observability features.
- Deployment of this sample before required production security, compliance, reliability, and operational controls are implemented and approved.
