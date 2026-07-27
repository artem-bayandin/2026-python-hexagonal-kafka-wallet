# Operations and release contract

## Current limitation

The repository is pre-implementation. The commands below are the required operating interface once the scaffold, Compose file, manifests, and services exist; they are not executable yet. An implementation is incomplete if it cannot satisfy this contract.

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

Local version 2:

```sh
docker compose --env-file backend/.env up -d postgres kafka worker
```

The worker must start only after migrations have completed and its readiness check confirms PostgreSQL and Kafka reachability. Shutdown must stop HTTP intake before stopping the worker, allow in-flight database transactions to finish, and leave unprocessed outbox records for retry.

## Health and observability

- `GET /health/live` proves the API process is running.
- `GET /health/ready` checks required dependencies and returns `503` while the application cannot serve traffic.
- Emit structured logs with request ID, correlation ID, operation ID, message ID, route, status, and duration. Never log secrets, OTPs, JWTs, or raw credentials.
- Emit metrics for HTTP latency/errors, database connectivity, outbox backlog, publication/consumption failures, operation outcomes, and worker retry age.
- Propagate correlation IDs from HTTP submission through the outbox, Kafka envelope, worker logs, diagnostics records, and operation queries.

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
- Retain structured logs and metrics sufficient to trace one operation from HTTP submission through Kafka to final balance/history state.
- Treat secret exposure, data corruption, and prolonged `503` readiness as incidents requiring documented response steps.
