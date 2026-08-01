# Initial Task — Technology-Agnostic Two-Version Wallet

**Status:** Starting brief for a new implementation

## Purpose

Create an educational custodial-wallet sample from the beginning in a programming language and ecosystem chosen later. This document specifies the product direction and delivery boundaries only; it intentionally does not prescribe a backend framework, frontend framework, database library, testing tool, deployment platform, or architecture style.

The wallet is delivered in two iterations. Version 1 proves the complete synchronous user journey. Version 2 evolves the money-moving operations to asynchronous Kafka processing while preserving the core business rules and user-facing history.

This is a learning sample, not a production-ready financial product. It must not claim to custody real money or assets, satisfy compliance obligations, or provide production-grade authorization, monitoring, or disaster recovery.

## Decisions to make before technical implementation

Before producing technology requirements or code, select:

1. The programming language and primary runtime (for example, Python, JavaScript/TypeScript, C#, Rust, or Go).
2. The system-design style. Hexagonal Architecture is the expected default because it keeps the business rules independent of HTTP, database, authentication, and Kafka adapters, but another style may be selected deliberately.
3. The UI approach, if a browser UI is in scope.
4. The relational database, migration tool, test approach, local-development environment, and operational tooling appropriate to the selected language.

The selected technology must support exact decimal money handling, safe concurrent balance updates, database transactions, Kafka producers and consumers, and automated tests.

## Product actors

### User

A user logs in using an email one-time password (OTP), sees wallet balances and personal transaction history, exchanges assets, withdraws assets, transfers assets to another user, and logs out.

### Admin operator

For the development sample, an admin operator authenticates through a specifically configured request header rather than as a user. The admin can see application/admin balances, see transactions across all users, and create a mock deposit for a selected user. This header-based access is development-only and must not be represented as production authorization.

## Shared business rules

- Initial assets are USD and USDT, with a currency catalog that provides each asset's supported decimal precision.
- Monetary values are decimal values represented without binary floating point or implicit rounding.
- Commands require positive amounts. Wallet balances cannot become negative.
- The sample exchange rate is fixed at 1 USDT = 1 USD. Exchange source and destination assets must differ and the result must be representable at the destination precision.
- Every deposit, exchange, withdrawal, and transfer creates one immutable business transaction with its financial terms, type, status, and timestamps.
- Balance changes and the corresponding transaction record are atomic.
- Concurrent operations must preserve balance invariants. The chosen persistence design must lock or otherwise coordinate affected balances deterministically before checking funds and applying a mutation.
- The API or interface must expose safe, stable errors and must never expose credentials, OTPs, tokens, or internal exception details.

## Version 1 — Synchronous wallet

Version 1 performs wallet mutations within the request/response interaction and returns the final outcome immediately.

### Authentication

- Request an OTP for an email address.
- Normalize the email and create a user on first request.
- Invalidate earlier active OTPs for that user.
- Use a six-digit OTP with a short expiry, single-use behavior, and a maximum failed-attempt limit.
- Verify an OTP and issue an authenticated user session and bearer token or equivalent session credential.
- Validate protected requests against both credential validity and active server-side session state.
- Let logout revoke only the current session.
- In development only, optionally display a demo OTP; do not send real email as part of this sample.

### User wallet

- View available balances by asset.
- View paginated personal transaction history.
- Exchange available funds between supported assets at the fixed 1:1 rate.
- Withdraw available funds, moving the amount from the user balance to the matching admin balance.
- Transfer an amount in one asset to another user identified by email.

### Admin wallet

- Authenticate development-only admin requests with a configured header.
- View admin/application balances.
- View paginated transaction history across all users.
- Create a mock deposit for a user by email, asset, and amount. A Version 1 deposit immediately credits that user's available balance and does not debit the admin balance.

### Version 1 outcome

A user can complete the full journey from OTP login through funded balance, exchange, withdrawal, or transfer, and can inspect the resulting history. An admin can fund users and inspect global wallet activity. Every completed money movement is synchronous and has a final result before the request returns.

## Version 2 — Kafka-backed asynchronous wallet

Version 2 changes every money-moving operation—admin deposit, user exchange, user withdrawal, and user transfer—to asynchronous command processing with Kafka.

### Direction

1. A request validates its shape and creates a pending operation/transaction plus an outbox record in one database transaction.
2. The request returns an accepted outcome and an operation identifier rather than a completed financial result.
3. An outbox relay publishes the command to Kafka.
4. Kafka messages use the affected user's identifier as a partition key so commands for one user retain order.
5. A worker consumes and executes deposit, exchange, withdrawal, and transfer commands.
6. The worker records a final `COMPLETED`, `REJECTED`, or `FAILED` outcome and updates balances atomically with that transition.
7. Clients poll operation status, balances, and history until the final outcome is available.

### Reliability and state expectations

- Use a transactional outbox because database commit and Kafka publication are not one distributed transaction.
- Assume at-least-once delivery. Use unique message and operation identifiers, inbox or processed-message records, and guarded state transitions so retries and duplicate deliveries do not apply money twice.
- Do not claim exactly-once end-to-end processing.
- A command accepted by the HTTP/API layer can later be rejected if current funds or state are no longer valid when the worker processes it.
- User balances must distinguish at least `available` and `pending`; an optional `rejected` bucket can support later withdrawal of rejected mock-deposit funds.
- Operation status, correlation identifiers, timestamps, and safe failure reason codes should be queryable.
- Optional development-only diagnostics may project sanitized message records from the database. Kafka must not be treated as a queryable historical database, and diagnostics must never reveal secrets.

### Version 2 outcome

Each of the four money-moving operations is submitted, published, processed, and finalized asynchronously. The implementation demonstrates ordered per-user processing, duplicate-message safety, business rejection distinct from infrastructure failure, and visible operation progress.

## Deliberate difference from this repository's current Version 2 notes

The existing implementation-reference documentation describes Kafka processing for deposits, exchanges, and withdrawals but leaves transfers synchronous. This initial task deliberately changes that target: a new implementation must include transfers in Version 2 Kafka processing as well. Generated requirements and implementation phases must carry that decision consistently through the API, operation lifecycle, message contracts, worker, persistence, tests, and UI.

## Non-goals

- Real money, cryptocurrency custody, banking, payment rails, or blockchain integrations.
- Real email delivery, production OTP security, passwords, refresh tokens, cookies, or MFA.
- Real AML or compliance-provider integrations.
- Market pricing, fees, slippage, or assets beyond the initial USD and USDT sample.
- Event sourcing, separate command/query databases, or a requirement for a mediator framework.
- WebSockets; polling is sufficient for Version 2.
- Production-safe admin access or public Kafka diagnostics.
- Exactly-once distributed processing.

## AI prompt — Create the documentation set

```text
Read docs/INITIAL_TASK.md as the authoritative starting brief for a new, technology-agnostic wallet implementation. Do not reuse the current repository's programming language, frameworks, or package choices as requirements.

First, ask me to select:
1. the programming language and runtime; and
2. the system-design style. Offer Hexagonal Architecture as the recommended default, but do not assume it unless I select it.

After I answer, create or propose a coherent documentation set before implementing code:
- functional requirements, including the Version 1 and Version 2 behavior and all four Version 2 Kafka operations: deposit, exchange, withdrawal, and transfer;
- technical requirements for the selected language, runtime, architecture, persistence, API, frontend if applicable, Kafka, configuration, and dependency policy;
- API or interaction contract, including authentication, errors, pagination, synchronous versus asynchronous responses, operation-status queries, and backward-compatibility rules;
- data model, money, concurrency, transaction-lifecycle, outbox/inbox, and idempotency requirements;
- configuration and environment-profile requirements, including development-only admin and diagnostics boundaries;
- operations and reliability guidance;
- automated testing strategy, including concurrency, Kafka ordering, duplicate delivery, rejection, retry, and failure scenarios;
- documentation index, authority, and change rules.

Keep the sample educational. State non-goals and do not imply production custody, real AML, real email, or exactly-once Kafka processing. Identify any unresolved product decision that materially changes behavior and ask me before choosing it.
```

## AI prompt — Create a phased implementation document

```text
Read docs/INITIAL_TASK.md and the approved requirements documents. Create an implementation-plan document; do not implement code yet.

First, ask me which feature packs to include and in what priority. Offer at least: scaffolding, authentication, admin wallet, user wallet, Version 1 integration/testing, Version 2 persistence and Kafka infrastructure, asynchronous operations, worker processing, diagnostics, UI updates, and reliability testing.

Turn the selected packs into ordered phases. Split every phase into small vertical features rather than horizontal technical layers. A vertical feature should state:
- the user/admin outcome;
- commands and queries;
- affected endpoint(s) and/or message command(s);
- domain/business rules;
- persistence and migration work;
- incoming and outgoing adapters, including UI when selected;
- tests across the relevant layers;
- dependencies on earlier slices; and
- concrete acceptance criteria or “done when” conditions.

Keep Version 1 synchronous. In Version 2, plan Kafka-backed submission and worker execution for deposit, exchange, withdrawal, and transfer. Include the transactional outbox, duplicate-safe processing, per-user ordering, operation-status queries, and failure/rejection behavior. Preserve the chosen architecture's dependency boundaries in every phase.
```
