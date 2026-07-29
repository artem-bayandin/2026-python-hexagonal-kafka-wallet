# Phase 2A — Insights (carry-forward reference)

Compact distillation of [PHASE_1_SCAFFOLDING.md](PHASE_1_SCAFFOLDING.md) and [PHASE_2_AUTHENTICATION.md](PHASE_2_AUTHENTICATION.md). Read this before Phases 3+ instead of re-reading the full Phase 1/2 guides.

Canonical behavior remains in [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md), [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md), [API_CONTRACT.md](../API_CONTRACT.md), and [CONFIGURATION.md](../CONFIGURATION.md).

## What is already done

### Phase 1 — Scaffolding

- Python backend (`backend/`) with `uv`, FastAPI, SQLAlchemy async, Alembic, ruff, mypy.
- React/Vite frontend (`frontend/`) with Yarn, ESLint, Vitest.
- Docker Compose PostgreSQL 18.
- Health endpoints: `GET /health/live`, `GET /health/ready`.
- Config via `pydantic-settings` in `backend/app/config.py`; secrets in gitignored `backend/.env`.

### Phase 2 — Authentication

- **Tables** (migration `23fa0ceb69ca`): `users`, `auth_sessions`, `otp_challenges`.
- **Endpoints:** `POST /auth/otp/request`, `POST /auth/otp/verify`, `POST /auth/logout`, `GET /health/authenticated`.
- **Domain:** `Result[T]`, OTP/auth entities, ports, use-case handlers.
- **Adapters:** `app/auth/` (HMAC OTP, PyJWT, system clock), `app/db/` (models, mappers, repositories).
- **API:** routers, Pydantic schemas, central error mapping, `ContextVarCurrentUserProvider`.
- **UI:** login flow, demo OTP display, token in `sessionStorage`, authenticated health check, logout.

### Not yet done

- Wallet tables, domain, repositories, handlers, routes, wallet UI.
- Kafka / Version 2.
- Automated tests (`backend/tests/` does not exist).

## Architectural invariants

These rules apply to every phase after authentication. Full rationale and examples live in Phase 2 § Architecture rules.

- **Hexagonal layers:** `domain/` (pure), `db/`, `auth/`, `api/`, `dependencies.py` (composition root). Domain never imports FastAPI, Pydantic, SQLAlchemy, PyJWT, or Kafka.
- **Façade imports:** cross-layer imports use package `__init__.py` façades only (`from app.domain import Result`, not `app.domain.entities.user`). Same-layer imports use relative paths through subpackage façades.
- **`Result[T]`:** every command/query handler returns `Result[T]`. Success payloads named `…Result`. Expected failures use `Result.failure(error_code)`; unexpected errors propagate for rollback. `reason` is internal only.
- **Transactions:** one `AsyncSession.begin()` per command. Returned `Result` (success or failure) commits; uncaught exceptions roll back. Handlers never call `commit()`/`rollback()`.
- **Naming:** repository collaborators `_repo`, service collaborators `_service`. DB implementations use `*Impl` suffix.
- **Use cases:** under `domain/use_cases/<entity>/`, not a shared `commands/` folder.
- **Current user:** authenticated handlers receive `CurrentUserProvider` by injection; commands do not repeat `current_user` fields. API binds via `bind_current_user` + `ContextVar`; reset in `finally`.
- **Error mapping:** only in `backend/app/api/exception_handlers.py`. Routes use `unwrap_result()` after executors return.
- **Money (when wallet logic starts):** `Decimal` + `NUMERIC` in PostgreSQL; per-currency precision from `currencies` table (USDT 8, USD 4); no silent rounding; amounts as decimal strings in JSON.
- **Concurrency (wallet):** wallet mutations use `SELECT … FOR UPDATE` in deterministic lock order; validate funds after locks.

## Old roadmap mapping

| New phase | [IMPLEMENTATION_STEPS.md](../IMPLEMENTATION_STEPS.md) | Notes |
| --- | --- | --- |
| Phase 1 | Step 1 | Done |
| Phase 2 | Steps 2–3, 6–7, 9 (auth subset), 10 (auth UI) | Done; tests deferred |
| Phase 3 | Step 5 (ORM models + migration subset) | Schema only, V1 wallet tables |
| Phase 4 | Steps 2, 4, 5 (repos), 8 (admin), 9 (admin routes), 10 (admin UI) | Full vertical slices |
| Phase 5 | Step 8 (user), 9 (user routes), 10 (wallet UI) | Full vertical slices |
| Phase 6 | Steps 12–16 | V2 schema + Kafka; draft doc for now |
| Phase 7 | Steps 11, 18 | All tests + CI; draft doc for now |

## Version boundaries (quick reference)

| Area | Version 1 (Phases 3–5) | Version 2 (Phase 6) |
| --- | --- | --- |
| Wallet mutations | Synchronous; `201 Created` with completed operation | Async via Kafka; `202 Accepted` |
| Balance buckets | single amount per wallet row | TBD — pending/rejected per currency |
| Transaction status | `completed` / `failed` | + `pending`, `rejected`, etc. |
| Extra tables | — | outbox, inbox, Kafka diagnostics |

## Pointers

- Phase 1 runnable steps: [PHASE_1_SCAFFOLDING.md](PHASE_1_SCAFFOLDING.md)
- Phase 2 runnable steps and architecture rules (full): [PHASE_2_AUTHENTICATION.md](PHASE_2_AUTHENTICATION.md)
- Next phase (schema): [PHASE_3_WALLET_SCHEMA.md](PHASE_3_WALLET_SCHEMA.md)
- Obsolete combined checklist: [IMPLEMENTATION_STEPS.md](../IMPLEMENTATION_STEPS.md) (superseded by phase guides for execution)
