# Wallet Sample — Functional Requirements

## 1. Purpose

Build a small custodial-wallet web application. It uses a React UI and a Python API to demonstrate OTP authentication, USDT/USD balances, mocked deposits, 1:1 exchange, withdrawals, user-to-user transfers, transaction history, Clean/Hexagonal Architecture, and CQRS.

The application is a learning sample. It does not move real money, send real email, perform real AML checks, or provide production-grade administration. [README.md](README.md) defines this document's authority and the reading order.

## 2. Actors

### 2.1 User

A user authenticates by email and OTP, views balances and transaction history, exchanges funds, withdraws funds, transfers funds to another user by email, and logs out.

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

## 5. Synchronous wallet

### 5.1 Mock deposit

The admin submits a user email, asset, and amount. The API creates any missing balance record and immediately credits the user's available balance.

A mock deposit creates demo funds. It does not debit the admin balance.

### 5.2 View balances

A user can view a list containing the current available balance for each supported asset. The admin can view the application/admin balance list.

### 5.3 Exchange

The user submits source asset, destination asset, and amount. The API validates asset support, precision, distinct assets, and sufficient source funds, then atomically debits the source balance and credits the destination balance at 1:1.

### 5.4 Withdraw

The user submits an asset and amount. The API atomically debits the user's available balance and credits the matching admin balance.

### 5.5 Transfer

The user submits a recipient email, asset, and amount. The API resolves the recipient by normalized email, rejects self-transfers, validates same-currency 1:1 movement and sufficient funds, then atomically debits the sender's wallet and credits the recipient's wallet.

### 5.6 Transaction history

One business transaction is created for each deposit, exchange, withdrawal, or transfer. Its financial terms are immutable. An exchange transaction records both source and destination assets and amounts. A transfer records the same asset on both sides at 1:1.

Users can view their own paginated history. Admin can view paginated history across all users. Transactions complete synchronously.

## 6. UI pages

The Vite/React/TypeScript application uses plain CSS and native `fetch`. The UI switches views with React state in `App.tsx` (no URL router wired yet); `react-router-dom` is installed as a scaffold dependency.

- **Login:** request OTP, display the demo OTP only in development, verify it, and establish the session.
- **Wallet:** show balances, paginated transaction history, submit exchanges, withdrawals, and transfers, show immediate results, and log out.
- **Admin:** development-only; capture the admin key, create deposits, and show admin balances and all transactions.

The JWT and demo admin key are kept in `sessionStorage` only for the development sample. This is intentionally simple and is not the recommended production security model.

## 7. Explicit non-goals

- Real cryptocurrency, banking, custody, or payment integrations.
- Real email delivery or production OTP security.
- Real AML providers or compliance decisions.
- Market prices, fees, slippage, or assets beyond USDT and USD.
- Refresh tokens, cookie authentication, MFA, or password login.
- Event sourcing or separate CQRS read/write databases.
- WebSockets.
- Production exposure of the Admin page.
- Deploying this sample before the required production controls are implemented and approved.
