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

## Version boundaries

| Area | Version 1 | Version 2 |
| --- | --- | --- |
| Wallet mutations | Execute synchronously and return completed results. | Submit an operation and return `202 Accepted`; the worker later completes, rejects, or fails it. |
| Balances | Single amount per wallet row. | Pending/rejected amounts per currency (strategy TBD). |
| Infrastructure | PostgreSQL. | PostgreSQL, Kafka, outbox relay, and worker. |
| Wallet feedback | Immediate result or error. | Pending operation ID and polling feedback. |
| Kafka diagnostics | Not present. | Development-only diagnostics, disabled outside development. |

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

One of the first docs created - [Wallet Proposal](docs/proposals/WALLET_SAMPLE_PROPOSAL_0.md). Contains some early stage requirements, gathered in a single file to start AI development from. When Version_1 was implemented, the doc was aligned with the code, and stored in [Wallet Proposal v1-aligned](docs/proposals/WALLET_SAMPLE_PROPOSAL_ALIGNED_V1.md).

Bite-sized notes on the “why” behind the code: patterns, trade-offs, and things worth remembering: [LEARN_PY](LEARN_PY.md)

Version 1 [Readme.md](docs/v1/README.md) and all the other v1 docs are in `/docs/v1/` folder.

Version 2 [Readme.md](docs/v2/README.md) with v2 requirements cut from v1 but not reviewed are in `/docs/v2-draft/` folder.

## Bootstrap and verification

Host processes (`uvicorn`, the Kafka worker, the reaper) read `backend/.env`. Local Kafka is reachable from the host at `127.0.0.1:29092` (`KAFKA_BOOTSTRAP_SERVERS` in `backend/.env.example`). Run the full demo only with `APP_ENV=development`; development-only OTP display, the demo admin credential, and Kafka diagnostics must be disabled in production.

### Terminal 1

Start PostgreSQL, Kafka, topics, migrations, and the API (terminal 1). `kafka-init` is a one-shot job that creates `wallet` (3 partitions) and `wallet_dlq`; it is not started by `up -d kafka` alone:

```sh
cd backend
uv sync --all-groups
cd ..
docker compose --env-file backend/.env up -d postgres
docker compose --env-file backend/.env up -d kafka
docker compose --env-file backend/.env run --rm kafka-init
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
```

### Terminal 2

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

### Terminal 3

Run the command worker that consumes `wallet` (terminal 3). It is a host process (`uv run python -m app.kafka.worker`), not a Compose service. The worker is the only application consumer; it publishes exhausted or poison failures to `wallet_dlq`. There is no long-running application consumer for `wallet_dlq` — that topic is for operations inspection and controlled replay:

```sh
cd backend
uv run python -m app.kafka.worker
```

Optional: inspect `wallet` or `wallet_dlq` with the broker console consumer (does not join `wallet_worker`):

```sh
docker compose --env-file backend/.env exec kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic wallet_dlq \
  --from-beginning
```

The stale-`submitted` reaper (`uv run python -m app.kafka.reaper` from `backend/`) is a later Version 2 process. It republishes to `wallet`; it does not consume either topic.

### Terminal 4 [optional]

```sh
cd backend
uv run python -m app.kafka.reaper
```

## Contribution and release policy

- Use `uv` in `backend/` and commit `backend/uv.lock`; enable Yarn with `corepack enable` and commit `frontend/yarn.lock`.
- Configure `frontend/.yarnrc.yml` with `nodeLinker: node-modules`, so frontend packages are installed under `frontend/node_modules` rather than Yarn Plug'n'Play.
- Change direct dependency ranges deliberately, refresh locks in a dedicated change, and run all quality gates before merging.
- Review generated Alembic migrations before applying them.
- Treat configuration, API, and database changes as documentation changes: update the relevant canonical document in the same change.
