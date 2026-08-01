# Clean Architecture Wallet

## Intro

This project presents a wallet code sample. 99.72% AI-coded under human guidance through the SDLC, with human review of docs and code.

The project will be built in two versions:

1. **Synchronous wallet processing** — Python hexagonal API, dockerized PostgreSQL, minimalistic React UI.
2. **Async transaction processing** — Kafka-based command pipeline.

## Status

- **Version 1** — implemented.
- **Version 1 documentation** — AI-updated to reflect the current codebase; not human-reviewed.
- **Version 2** — docs to be created.

## Functional requirements

- User should be able to log in with OTP.
- User should be able to view balances and transactions.
- User should be able to exchange assets, transfer to another user, and withdraw.
- Admin should be able to log in with a custom temp dev key.
- Admin should be able to see balances and all transactions.
- Admin should be able to deposit initial funds for a user.

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

One of the first docs created - [Wallet Proposal](docs/proposals/WALLET_SAMPLE_PROPOSAL_0.md). Contains some early stage requirements, gathered in a single file to start AI development from. When Version_1 was implemented, the doc was aligned with the code, and stored in [Wallet Proposal v1-aligned](docs/proposals/WALLET_SAMPLE_PROPOSAL_ALIGNED_V1.md)

Start with [the documentation index](docs/README.md). The canonical documents are:

1. [Functional requirements](docs/FUNCTIONAL_REQUIREMENTS.md) — product behavior and non-goals.
2. [Technical requirements](docs/TECHNICAL_REQUIREMENTS.md) — architecture, dependencies, quality constraints, and security boundaries.
3. [API contract](docs/API_CONTRACT.md) — stable HTTP payload, pagination, status, and error conventions.
4. [Configuration](docs/CONFIGURATION.md) — environment variables, profiles, local ports, and secret handling.
5. [Operations](docs/OPERATIONS.md) — lifecycle, migration, release, rollback, backup, observability, and incident expectations.
6. [Implementation steps](docs/IMPLEMENTATION_STEPS.md) — build order and verification criteria.

## Bootstrap and verification

Run database and api (teminal 1):

```sh
cd backend
uv sync --all-groups
cd ..
docker compose --env-file backend/.env up -d postgres
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
```

Run frontend (terminal 2):

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
