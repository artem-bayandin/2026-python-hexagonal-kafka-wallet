# Clean Architecture Wallet

## About

This project presents a wallet code sample (instead of a hackneyed ToDo list). Designed by Human; Led, Reviewed, and Fixed by Human; Coded by AI under the Human's management.

## Goals

- create a code sample to be presented to future investors, teams, and tech interviewers
- use `python` for `hexagonal` web api
- use `kafka` within a `docker` container for async message processing
- use `postgresql` within a `docker` container as the database
- lead `AI` software development from zero to hero, with 80%+ of code to be created by AI

## Roadmap

The project will be built in several versions, gradually incrementing enterprise readiness level:

1. **Synchronous wallet processing** [completed] — Python hexagonal API, dockerized PostgreSQL, minimalistic React UI.
2. **Async transaction processing** [completed] — Kafka-based command pipeline with data changes notifications.
3. **TBD** **[optional]** system code review
4. **TBD** **[optional]** improve docker connetion: move from Plaintext to Sasl-ssl, explore more config variables
5. **TBD** **[optional]** database sharding
6. **TBD** **[optional]** kubernetes cluster
7. **TBD** **[optional]** load balancer
8. **TBD** **[optional]** metrics (prometheus, open telemetry, kafka connect, etc.)

## Status

- **Version 1** — implemented, [release v1.0.0](https://github.com/artem-bayandin/2026-python-hexagonal-kafka-wallet/releases/tag/release-v1.0.0)
- **Version 2** — implemented, [release v1.1.0](https://github.com/artem-bayandin/2026-python-hexagonal-kafka-wallet/releases/tag/release-v1.1.0).

Version 1.1.0 video presentation:

![play](images/20260825-184820.gif)

## Functional requirements

- User should be able to log in with OTP.
- User should be able to view its balances and transactions.
- User should be able to exchange its own assets, transfer to another user, and withdraw to admin wallet.
- Admin should be able to log in with a custom temp dev key.
- Admin should be able to see admin balances and all transactions.
- Admin should be able to deposit initial funds to a user.

## Version boundaries

| Area | Version 1 | Version 2 |
| --- | --- | --- |
| Wallet mutations | Execute synchronously and return completed results. | Submit an operation and return `202 Accepted`; the worker later completes, rejects, or fails it. |
| Balances | Single amount per wallet row. | Pending/rejected amounts per currency. |
| Infrastructure | PostgreSQL. | PostgreSQL, Kafka, outbox relay, and worker. |
| Wallet feedback | Immediate result or error. | Pending operation ID and polling feedback. |
| Diagnostics | Not present. | Not present. |
| Tests | Not present. | Not present. |

## Documentation

One of the first docs created - [Wallet Proposal](docs/archive/proposals/WALLET_SAMPLE_PROPOSAL_0.md). Contains some early stage requirements, gathered in a single file to start AI development from. When Version_1 was implemented, the doc was aligned with the code, and stored in [Wallet Proposal v1-aligned](docs/archive/proposals/WALLET_SAMPLE_PROPOSAL_ALIGNED_V1.md).

Version 1 [Readme.md](docs/archive/v1/README.md) and all the other v1 docs are in `/docs/v1/` folder.

Version 2 [Readme.md](docs/archive/v2/README.md) and all the other v2 docs are in `/docs/v2/` folder.

## Bootstrap and verification

Host processes (`uvicorn`, the Kafka wallet worker, the reaper) read `backend/.env`. Local Kafka is reachable from the host at `127.0.0.1:29092` (`KAFKA_BOOTSTRAP_SERVERS` in `backend/.env.example`). Run the full demo only with `APP_ENV=development`; development-only OTP display, the demo admin credential, and Kafka diagnostics must be disabled in production.

### .env

- copy `backend/.env.example` into `backend/.env`
- copy `frontend/.env.example` into `frontend/.env`
- for some processes, a symlink might exist in the root `.env` to target `backend/.env`

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

### Terminal 3

Run the command worker that consumes `wallet` (terminal 3). It is a host process (`uv run python -m app.kafka.workers.wallet`), not a Compose service. The worker is the only application consumer; it publishes exhausted or poison failures to `wallet_dlq`. There is no long-running application consumer for `wallet_dlq`.

```sh
cd backend
uv run python -m app.kafka.workers.wallet
```

Optional: inspect `wallet` or `wallet_dlq` with the broker console consumer (does not join `wallet_worker`):

```sh
docker compose --env-file backend/.env exec kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic wallet_dlq \
  --from-beginning
```

### Terminal 4 [optional]

The stale-`submitted` reaper (`uv run python -m app.kafka.workers.reaper` from `backend/`) republishes to `wallet`; it does not consume either topic.

```sh
cd backend
uv run python -m app.kafka.workers.reaper
```

### Optional commands

- `docker compose --env-file backend/.env down -v --remove-orphans` - (from the repo root) removes stops postgres/kafka, removes the containers (and their logs), and deletes the postgres_data and kafka_data volumes
- `docker compose --env-file backend/.env up -d --force-recreate kafka` - recreate kafka

## Repository layout (v1.1.0)

```
project-root/
├── backend/                              # Python Hexagonal API, Kafka workers, DB migrations
│   ├── alembic/
│   ├── app/
│   │   ├── api/
│   │   │   ├── executors/
│   │   │   ├── routers/
│   │   │   ├── schemas/
│   │   │   ├── admin_transaction_cursor_codec.py
│   │   │   ├── current_user_provider.py
│   │   │   ├── db_session.py
│   │   │   ├── dependencies.py
│   │   │   ├── exception_handlers.py
│   │   │   ├── formatting.py
│   │   │   ├── result_mapping.py
│   │   │   └── sse_status_encoder.py
│   │   ├── auth/
│   │   │   ├── jwt_service.py
│   │   │   ├── otp_service.py
│   │   │   └── system_clock.py
│   │   ├── db/
│   │   │   ├── mappers/
│   │   │   ├── models/
│   │   │   ├── repositories/
│   │   │   └── session.py
│   │   ├── domain/
│   │   │   ├── messaging/
│   │   │   ├── ports/
│   │   │   │   ├── repositories/
│   │   │   │   ├── services/
│   │   │   │   └── current_user_provider.py
│   │   │   ├── read_models/
│   │   │   ├── use_cases/
│   │   │   │   ├── admin/
│   │   │   │   │   ├── deposit/
│   │   │   │   │   │   ├── admin_deposit_cmd.py
│   │   │   │   │   │   ├── execute_deposit.py
│   │   │   │   │   │   └── submit_deposit.py
│   │   │   │   │   ├── admin_balances_query.py
│   │   │   │   │   └── admin_transactions_query.py
│   │   │   │   ├── auth_session/
│   │   │   │   │   └── logout_cmd.py
│   │   │   │   ├── currency/
│   │   │   │   │   └── currencies_query.py
│   │   │   │   ├── otp/
│   │   │   │   │   ├── request_otp_cmd.py
│   │   │   │   │   └── verify_otp_cmd.py
│   │   │   │   ├── recovery/
│   │   │   │   │   └── reap_stale_submitted.py
│   │   │   │   ├── sub_exec_base/
│   │   │   │   │   ├── execute_cmd.py
│   │   │   │   │   └── submit_transaction.py
│   │   │   │   ├── user/
│   │   │   │   │   ├── current_user_query.py
│   │   │   │   │   ├── user_balances_query.py
│   │   │   │   │   ├── user_transactions_query.py
│   │   │   │   │   └── users_query.py
│   │   │   │   └── wallet/
│   │   │   │       ├── exchange/
│   │   │   │       │   ├── exchange_cmd.py
│   │   │   │       │   ├── execute_exchange.py
│   │   │   │       │   └── submit_exchange.py
│   │   │   │       ├── transfer/
│   │   │   │       │   ├── execute_transfer.py
│   │   │   │       │   ├── submit_transfer.py
│   │   │   │       │   └── transfer_cmd.py
│   │   │   │       └── withdraw/
│   │   │   │           ├── execute_withdrawal.py
│   │   │   │           ├── submit_withdrawal.py
│   │   │   │           └── withdraw_cmd.py
│   │   │   ├── value_objects/
│   │   │   ├── current_user.py
│   │   │   ├── error_codes.py
│   │   │   ├── result.py
│   │   │   ├── safe_errors.py
│   │   │   └── token_claims.py
│   │   ├── kafka/
│   │   │   ├── runtime/
│   │   │   │   ├── process.py
│   │   │   │   └── readiness.py
│   │   │   ├── shared/
│   │   │   ├── topics/
│   │   │   │   ├── dlq/
│   │   │   │   └── wallet/
│   │   │   └── workers/
│   │   │       ├── dlq/
│   │   │       ├── reaper/
│   │   │       ├── wallet/
│   │   │       └── visibility.py
│   │   ├── notifier/
│   │   │   ├── adapters/
│   │   │   │   ├── pg_admin_status_listener.py
│   │   │   │   └── pg_notifier.py
│   │   │   ├── ports/
│   │   │   │   ├── admin_status_listener.py
│   │   │   │   ├── status_event_repository.py
│   │   │   │   └── status_notifier.py
│   │   │   ├── asyncpg_url.py
│   │   │   └── status_event.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   └── main.py
│   ├── .env
│   ├── .env.example
│   ├── .gitignore
│   ├── .python-version
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── uv.lock
│
├── frontend/                             # React UI (Yarn, Vite)
│
├── docs/                                 # Canonical requirements and implementation guides
│
├── images/                               # Files for docs
│
├── .gitignore
├── docker-compose.yml
├── LICENSE
├── pyrightconfig.json
└── README.md
```
