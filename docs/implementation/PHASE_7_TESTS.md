# Phase 7 — Tests and CI

**Status:** Draft — high-level intentions only. Detailed step-by-step guide to be written when implementation phases are far enough along to test meaningfully (at minimum after Phase 5; Kafka tests after Phase 6).

Read [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md). Phases 2–6 deliberately defer automated tests to this phase.

## Purpose

Introduce **automated test coverage** and optional **CI/pre-commit** gates so the sample can be verified repeatably without manual curl/browser checks alone.

## Prerequisites

- Phase 5 complete for Version 1 integration coverage baseline.
- Phase 6 complete for Version 2 Kafka integration coverage.

## Intended scope

### Test layout

Create under `backend/tests/`:

- `unit/` — domain handlers, `Money` precision, OTP/JWT adapters, result/error mapping;
- `integration/` — PostgreSQL via `testcontainers`, Alembic migrate-from-zero per test session, repository round-trips, HTTP via HTTPX.

Frontend (minimal):

- Vitest tests for login, auth header attachment, admin header attachment, one wallet command (per [IMPLEMENTATION_STEPS.md](../IMPLEMENTATION_STEPS.md) Step 10).

### Coverage targets

| Area | Source of deferred tests |
| --- | --- |
| Authentication | Phase 2 (Steps 3, 6, 7 unit tests) |
| Wallet domain | Phase 4/5 command/query handlers with fake repos |
| Persistence | Phase 3+ repository integration, precision round-trip |
| Concurrency | Parallel withdrawal/exchange — no negative balances |
| Version 1 E2E | Deposit, both exchange directions, both withdrawal assets, user/admin history |
| Version 2 Kafka | Outbox publish, worker process, ordering per user, duplicate message idempotency, relay retry |
| API | Error envelopes, pagination cursors, no secret leakage in diagnostics |

### Tooling (already in scaffold)

- pytest, pytest-asyncio, HTTPX, `testcontainers[postgres]`;
- ruff, mypy (strict);
- frontend Vitest + Testing Library.

### CI / pre-commit (optional)

Per [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md):

- pre-commit: ruff, mypy, fast unit tests;
- CI: backend lint/typecheck/tests, frontend typecheck/tests/build, PostgreSQL integration, Version 2 Kafka integration when applicable.

## Explicit non-goals

- 100% line coverage;
- load/stress testing beyond concurrency overspend proof.

## Done when (target)

`uv run pytest` and `yarn test:run` pass locally and in CI; a clean testcontainers database migrates from zero through all revisions; concurrent debit test proves no negative balance; Kafka duplicate-delivery test proves idempotent worker behavior.

## Relationship to earlier phases

When implementing Phases 3–6, use manual verification checklists in each phase guide. Do not add `backend/tests/` files until this phase unless explicitly pulling test work forward.
