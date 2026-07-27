# Clean Architecture Wallet

## Status

This repository is an educational wallet sample. The version-1 foundation is implemented: the Python/FastAPI and Vite/React scaffolds, validated configuration, PostgreSQL Compose service, health endpoints, dependency locks, and framework-free money rules are available. Authentication, persistence, and wallet workflows remain to be implemented. Do not treat it as a production-deployable service.

The target is a two-version Python/React wallet sample:

- version 1 executes wallet commands synchronously against PostgreSQL;
- version 2 submits those commands asynchronously through a transactional outbox and Kafka worker.

The developer implements the sample. AI may help with planning, explanation, review, and diagnosis when requested.

## Repository layout

```
project-root/
├── backend/          # Python API (uv, FastAPI, Alembic, tests)
├── frontend/         # React UI (Yarn, Vite)
├── docs/             # Canonical requirements and implementation guides
├── docker-compose.yml
└── README.md
```

## Documentation

Start with [the documentation index](docs/README.md). The canonical documents are:

1. [Functional requirements](docs/FUNCTIONAL_REQUIREMENTS.md) — product behavior and non-goals.
2. [Technical requirements](docs/TECHNICAL_REQUIREMENTS.md) — architecture, dependencies, quality constraints, and security boundaries.
3. [API contract](docs/API_CONTRACT.md) — stable HTTP payload, pagination, status, and error conventions.
4. [Configuration](docs/CONFIGURATION.md) — environment variables, profiles, local ports, and secret handling.
5. [Operations](docs/OPERATIONS.md) — lifecycle, migration, release, rollback, backup, observability, and incident expectations.
6. [Implementation steps](docs/IMPLEMENTATION_STEPS.md) — build order and verification criteria.

## Bootstrap and verification

No command can run successfully until Step 1 of the implementation plan creates the listed artifacts. Once the scaffold exists, the supported local workflow is:

```sh
cd backend
uv sync --all-groups
cd ..
docker compose --env-file backend/.env up -d postgres
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
```

In a second terminal:

```sh
cd frontend
corepack enable
yarn install --immutable
yarn dev
```

The quality gates are:

```sh
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
uv run pytest
cd ../frontend && yarn lint && yarn typecheck && yarn test && yarn build
```

Version 2 additionally requires the `kafka` and `worker` Compose services. Run the full demo only with `APP_ENV=development`; development-only OTP display, the demo admin credential, and Kafka diagnostics must be disabled in production.

## Contribution and release policy

- Use `uv` in `backend/` and commit `backend/uv.lock`; enable Yarn with `corepack enable` and commit `frontend/yarn.lock`.
- Configure `frontend/.yarnrc.yml` with `nodeLinker: node-modules`, so frontend packages are installed under `frontend/node_modules` rather than Yarn Plug'n'Play.
- Change direct dependency ranges deliberately, refresh locks in a dedicated change, and run all quality gates before merging.
- Review generated Alembic migrations before applying them.
- Treat configuration, API, and database changes as documentation changes: update the relevant canonical document in the same change.
