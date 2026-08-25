# Operations and release contract

## Current status

Version 1 (Phases 1–5) is implemented: backend, frontend, PostgreSQL schema, auth, admin wallet, and user wallet flows run locally with the commands below. Automated test suites and CI are not yet complete.

## Service lifecycle

Local version 1:

```sh
cd backend
uv sync --all-groups
cd ..
docker compose --env-file backend/.env up -d postgres
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
```

## Health and observability

- `GET /health/live` proves the API process is running.
- `GET /health/ready` checks required dependencies and returns `503` while the application cannot serve traffic.
- Emit structured logs with request ID, route, status, and duration. Never log secrets, OTPs, JWTs, or raw credentials.
- Emit metrics for HTTP latency/errors and database connectivity.

## Database migrations and recovery

Before applying a migration:

1. Generate it with `uv run alembic revision --autogenerate -m "<summary>"` from `backend/`.
2. Review generated DDL, indexes, constraints, locks, and downgrade behavior.
3. Test upgrade from a production-like backup and test rollback or forward-fix.
4. Apply with `uv run alembic upgrade head`.

Take and verify a logical PostgreSQL backup before every production schema change. The implementation must provide a documented `pg_dump` command and a tested restore procedure matched to the pinned PostgreSQL major version. Destructive schema changes require an expand/migrate/contract sequence, not a single breaking deployment.

## Release and rollback

Every release must:

1. Build from committed lockfiles and immutable container image digests.
2. Pass backend lint, format, type, unit, integration, and migration tests.
3. Pass frontend lint, typecheck, test, and production build.
4. Apply reviewed migrations before enabling new application code.
5. Verify health endpoints and a smoke test of auth and one wallet command.

Rollback application code only when the database schema remains compatible. Otherwise use a tested forward-fix or restore procedure. Never roll back a schema migration blindly after data has been written by the newer application.

## Backup and incident response

- Take logical PostgreSQL backups on a schedule matched to recovery objectives; verify restore regularly.
- Retain structured logs and metrics sufficient to trace one operation through its HTTP request to final balance/history state.
- Treat secret exposure, data corruption, and prolonged `503` readiness as incidents requiring documented response steps.
