# Phase 1 — Kafka infrastructure

Stand up the Kafka foundation for Version 2 without changing any Version 1 wallet behavior: a pinned local broker, explicitly provisioned topics, validated per-process settings, a producer adapter with the required guarantees, and independently runnable worker and reaper process shells.

Work in this order:

1. `dependency-and-image-selection`
2. `compose-broker-and-topics`
3. `settings`
4. `domain-ports-and-envelope`
5. `producer-adapter`
6. `process-shells`
7. `readiness`
8. `smoke-check`

## Current implementation status

- **Steps 1–5 complete (2026-08-05); Steps 6–8 not started.** Version 1 (FastAPI, React, PostgreSQL, Alembic, synchronous wallet mutations) is the running baseline.
- Prerequisite gate from [IMPLEMENTATION_STEPS.md](../v2/IMPLEMENTATION_STEPS.md) §Prerequisites is green: Version 1 reproduces from a clean checkout, the Alembic baseline head (`d377d8c90992`) is recorded, baseline quality-command failures are written down, and an implementation branch with a rollback point exists.

Canonical behavior is defined by [README.md](../v2/README.md), [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §3/§5/§9, [CONFIGURATION.md](../v2/CONFIGURATION.md) §4/§5/§10–§12, and [API_CONTRACT.md](../v2/API_CONTRACT.md) §Diagnostics and health.

## Purpose

Make Kafka infrastructure reproducible, secured by configuration boundaries, observable, and independently runnable — proven by a one-time smoke check — while no wallet route publishes anything and no worker mutates balances.

## Prerequisites

- Version 1 builds, migrates, and runs locally (`docker compose up -d postgres`, `uv run alembic upgrade head` from `backend/`).
- Broker and Python client choices are mutually compatible, maintained, and vulnerability-reviewed (Step 1 records the decision).
- Local network topology, topic ownership, process ownership, and secret boundaries from [CONFIGURATION.md](../v2/CONFIGURATION.md) §10–§12 are agreed.

## Scope

### In scope

- Pinned Kafka broker in `docker-compose.yml` with health check, named volume, no public listener by default.
- Explicit provisioning of `wallet` (3 local partitions) and `wallet_dlq`; no reliance on broker auto-creation.
- Async Kafka client dependency in `backend/pyproject.toml` with updated `uv.lock`.
- Validated settings for Kafka connection, topics, producer reliability, worker, reaper, SSE, and admin polling, with startup failure on invalid combinations.
- Domain publisher port, clock port reuse, transport-neutral command envelope, transaction-type validation.
- Producer adapter with `acks=all`, idempotence, bounded retries/backoff, bounded delivery timeout, mandatory key.
- Worker and reaper process shells (no execution or republication logic yet).
- Per-process readiness checks.

### Out of scope

- Any schema change (Phase 2).
- Any wallet route publishing, worker execution, retry/DLQ behavior, or reaper scans (Phase 3+).
- Any product UI change.
- Automated tests and CI (deferred per [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §15).

## Done when

Kafka infrastructure is reproducible, secured by configuration boundaries, observable, independently runnable, and proven by the smoke check — without changing Version 1 wallet behavior.

## Architecture rules

- Follow [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §4: `domain/` must not import FastAPI, Pydantic, SQLAlchemy, or Kafka-client packages. The envelope model and publisher port live in `domain/`; all Kafka-client code lives under `app/kafka/`.
- Topic names, group ID, and key rules are deployment configuration with documented local defaults (`KAFKA_COMMAND_TOPIC=wallet`, `KAFKA_DLQ_TOPIC=wallet_dlq`, `KAFKA_WORKER_GROUP_ID=wallet_worker`); startup validation requires non-empty values, distinct command/DLQ topics, and matching broker provisioning.
- Every published record has a non-empty key: submitting user UUID string for user commands, literal `admin` for deposits. A publish call without a key is rejected before any network I/O.
- Producer guarantees are not feature flags: `acks=all` and idempotence are always on; retries and delivery timeout are bounded by settings.
- Processes validate only the settings they own ([CONFIGURATION.md](../v2/CONFIGURATION.md) §10) and fail startup on an unknown profile, missing owned setting, topic mismatch, incompatible timeout relationship, or a prohibited production shortcut.
- Pin the broker image by exact tag or immutable digest; pin the client in `uv.lock`. No floating versions.
- Keep every Kafka connection and credential value out of frontend build variables and assets (`VITE_*` stays limited to `VITE_API_BASE_URL`).

## Step 1 — Dependency and image selection

Pinned selections (rollback restores these exact versions):

- **Broker image:** `apache/kafka:4.3.1` (KRaft mode, single node locally). CLI tools at `/opt/kafka/bin/` (verified against the pinned image).
- **Python client:** `aiokafka==0.14.0` (`backend/pyproject.toml`, `uv.lock`).

Commands:

```bash
cd backend
uv add aiokafka
uv lock
```

Review broker/client protocol compatibility (aiokafka supported broker versions) and run a vulnerability review of the resolved graph:

```bash
cd backend
uv tree | grep -i kafka
```

Note the pinned client version and broker tag in this file once selected, so rollback restores the exact prior dependency graph.

**Decision record (2026-08-05, Step 1 complete):**

- Broker: `apache/kafka:4.3.1` confirmed published on Docker Hub (multi-arch amd64/arm64, index digest `sha256:77e3df9054047a88b520d0cc46e16696d3b22022e1d580aeccd2632df6532837`); CLI tools live at `/opt/kafka/bin/` in this image.
- Client: `aiokafka==0.14.0` added to `backend/pyproject.toml` and pinned in `backend/uv.lock` (exact pin, not a range). Transitive graph is minimal: `async-timeout==5.0.1`, `packaging==26.2`, `typing-extensions==4.16.0`.
- Protocol compatibility: aiokafka 0.14.0 negotiates API versions per connection and is verified working against Kafka 4.x brokers (KIP-896 old-protocol removal handled); compatible with the 4.3.1 broker.
- Vulnerability review of the resolved graph: no known vulnerabilities reported for `aiokafka 0.14.0` (Sonatype Guide / ReversingLabs scans, checked 2026-08-05); transitive deps are small, maintained utility packages with no outstanding advisories.
- Rollback anchor: pre-Phase-1 `pyproject.toml`/`uv.lock` (without `aiokafka`) is the recorded rollback state.

## Step 2 — Compose broker and topics

Update `docker-compose.yml` — add a `kafka` service in KRaft single-node mode with a health check and named volume, and a one-shot `kafka-init` service that provisions both topics explicitly. Keep Kafka internal to the Compose network; do not publish a host port by default (an optional `127.0.0.1:29092` listener may be added only temporarily for local debugging).

```yaml
services:
  postgres:
    # ... unchanged Version 1 service ...

  kafka:
    image: apache/kafka:<exact-tag>
    environment:
      KAFKA_NODE_ID: "1"
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_LISTENERS: PLAINTEXT://kafka:9092,CONTROLLER://kafka:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: "1"
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
      KAFKA_LOG_DIRS: /var/lib/kafka/data
    volumes:
      - kafka_data:/var/lib/kafka/data
    healthcheck:
      test: ["CMD-SHELL", "/opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server kafka:9092 > /dev/null 2>&1"]
      interval: 5s
      timeout: 5s
      retries: 12
      start_period: 10s

  kafka-init:
    image: apache/kafka:<exact-tag>
    depends_on:
      kafka:
        condition: service_healthy
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic wallet --partitions 3 --replication-factor 1
        /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic wallet_dlq --partitions 1 --replication-factor 1
        /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic wallet
        /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic wallet_dlq
    restart: "no"

volumes:
  postgres_data:
  kafka_data:
```

Verify exact CLI paths (`/opt/kafka/bin/`) against the pinned image and adjust once, keeping the change pinned and documented. `KAFKA_AUTO_CREATE_TOPICS_ENABLE=false` plus explicit provisioning ensures nothing relies on broker auto-creation.

Bring the stack up and confirm:

```bash
docker compose up -d kafka
docker compose run --rm kafka-init
docker compose ps
```

**Verification record (2026-08-05, Step 2 complete):** CLI paths `/opt/kafka/bin/` confirmed against `apache/kafka:4.3.1` (health check passes, `kafka-topics.sh` runs unmodified). `docker compose up -d kafka` → healthy; `docker compose run --rm kafka-init` → created `wallet` (3 partitions, RF 1) and `wallet_dlq` (1 partition, RF 1), both described in output above. `docker compose ps` shows Kafka healthy with `9092/tcp` internal only — no host port published. The broker's one-time metric-name warning about `.`/`_` topic collision is informational; `wallet` and `wallet_dlq` do not collide.

## Step 3 — Settings

Update `backend/app/config.py` — add the Version 2 settings groups using `pydantic-settings`, following the existing `Settings` pattern. Each process validates only the settings it owns.

Add these variables exactly as named in [CONFIGURATION.md](../v2/CONFIGURATION.md):

| Group | Variables |
| --- | --- |
| Kafka connection (API, worker, reaper) | `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_COMMAND_TOPIC` (default `wallet`), `KAFKA_SECURITY_PROTOCOL` (default `PLAINTEXT`), `KAFKA_SASL_MECHANISM`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, `KAFKA_SSL_CA_FILE`, `KAFKA_SSL_CERT_FILE`, `KAFKA_SSL_KEY_FILE` |
| Topics / group | `KAFKA_DLQ_TOPIC` (default `wallet_dlq`, worker), `KAFKA_WORKER_GROUP_ID` (default `wallet_worker`, worker) |
| Producer reliability (API, worker for DLQ, reaper) | `KAFKA_PRODUCER_REQUEST_TIMEOUT_MS` (`10000`), `KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS` (`30000`), `KAFKA_PRODUCER_MAX_RETRIES` (`5`), `KAFKA_PRODUCER_RETRY_BACKOFF_MS` (`200`), `KAFKA_PRODUCER_RETRY_BACKOFF_MAX_MS` (`2000`) |
| Worker | `WORKER_MAX_ATTEMPTS` (`3`), `WORKER_RETRY_BACKOFF_MS` (`500`), `WORKER_RETRY_BACKOFF_MAX_MS` (`5000`), `WORKER_POLL_TIMEOUT_MS` (`1000`), `WORKER_HEARTBEAT_INTERVAL_MS` (`3000`), `WORKER_SESSION_TIMEOUT_MS` (`30000`), `WORKER_MAX_POLL_INTERVAL_MS` (`300000`) |
| Reaper | `REAPER_INTERVAL_SECONDS` (`30`), `REAPER_STALE_THRESHOLD_SECONDS` (`60`), `REAPER_BATCH_SIZE` (`100`, 1–1000) |
| API streaming / polling | `ADMIN_LONG_POLL_DEFAULT_SECONDS` (`25`), `ADMIN_LONG_POLL_MAX_SECONDS` (`30`), `SSE_HEARTBEAT_INTERVAL_SECONDS` (`15`), `SSE_RETRY_MILLISECONDS` (`3000`, ≥ 3000) |

Implement the cross-setting invariants from [CONFIGURATION.md](../v2/CONFIGURATION.md) §14 as validators that raise at startup:

- command and DLQ topic names are non-empty and distinct;
- `KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS >= KAFKA_PRODUCER_REQUEST_TIMEOUT_MS`; retry backoff max ≥ initial backoff;
- `WORKER_MAX_ATTEMPTS` is positive; `WORKER_HEARTBEAT_INTERVAL_MS < WORKER_SESSION_TIMEOUT_MS`; `WORKER_MAX_POLL_INTERVAL_MS` covers worst-case local processing plus the full retry schedule;
- `REAPER_STALE_THRESHOLD_SECONDS` exceeds the producer delivery bound plus jitter (validate `REAPER_STALE_THRESHOLD_SECONDS * 1000 > KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS`);
- `ADMIN_LONG_POLL_DEFAULT_SECONDS <= ADMIN_LONG_POLL_MAX_SECONDS`;
- in `APP_ENV=production`: `KAFKA_SECURITY_PROTOCOL` is `SSL` or `SASL_SSL`, SASL/mutual-TLS pairs are complete and readable, `ADMIN_API_KEY` and `ENABLE_DEMO_OTP=true` are rejected.

Suggested structure in `backend/app/config.py`:

```python
class KafkaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAFKA_")
    bootstrap_servers: str
    command_topic: str = "wallet"
    dlq_topic: str = "wallet_dlq"
    worker_group_id: str = "wallet_worker"
    security_protocol: Literal["PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL"] = "PLAINTEXT"
    # ... sasl/ssl fields, producer timeout/retry fields, and validators per above ...
```

Also update `.env.example` (or the documented local env template) with the development values: `KAFKA_BOOTSTRAP_SERVERS=kafka:9092` when the API runs in Compose, or the host-reachable address when run locally against the Compose broker.

**Implementation record (2026-08-05, Step 3 complete):** `backend/app/config.py` now defines `SharedSettings` (APP_ENV/DATABASE_URL/LOG_LEVEL, owned by every process), `Settings` (API, unchanged public surface, plus rejection of `ADMIN_API_KEY` in production and `ENABLE_DEMO_OTP=true` outside development), `KafkaSettings` (`KAFKA_` prefix: connection, topic/group names with local defaults, SASL/SSL pairing, producer reliability bounds), `WorkerSettings` (`WORKER_` prefix), `ReaperSettings` (`REAPER_` prefix), and `StreamingSettings` (admin long-poll/SSE, no prefix). Cross-group invariants live in `validate_kafka_connection` / `validate_worker_composition` / `validate_reaper_composition`, applied by the per-process `load_api_runtime` / `load_worker_runtime` / `load_reaper_runtime` loaders so each process validates only what it owns and fails at startup on any violation. `WORKER_MAX_POLL_INTERVAL_MS` must cover one poll plus the full retry schedule plus the bounded DLQ publication wait. Empty strings normalize to missing. `.env.example` documents all development values (`KAFKA_BOOTSTRAP_SERVERS=kafka:9092`, Compose-network address). Verified: `ruff check`, `ruff format --check`, `mypy app` pass; validator matrix (topic distinctness, timeout orderings, SASL/SSL pairing, production protocol/CA/admin-key/demo-OTP rejection, reaper/worker composition bounds) all reject/accept as specified; `create_app` still boots with existing Version 1 settings.

## Step 4 — Domain ports and envelope

Create `backend/app/domain/messaging/__init__.py` and `backend/app/domain/messaging/command_envelope.py` — framework-free, no Kafka imports:

```python
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class CommandType(StrEnum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    EXCHANGE = "exchange"
    TRANSFER = "transfer"


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    request_id: UUID
    type: CommandType
    submitted_at: datetime
```

Create `backend/app/domain/ports/services/command_publisher.py`:

```python
from typing import Protocol

from ...messaging.command_envelope import CommandEnvelope


class CommandPublisher(Protocol):
    async def publish(self, *, key: str, envelope: CommandEnvelope) -> None: ...
```

`publish` returns only after broker acknowledgement and raises on definitive bounded failure; a `None` or empty `key` is rejected by the adapter before network I/O. Reuse the existing clock service port (`domain/ports/services/clock_service.py`) for `submitted_at`; do not add a second clock.

Envelope validation rules (domain level): `type` is exactly one of the four command types; `submitted_at` is timezone-aware UTC; `request_id` is a UUID. Parsing helpers that tolerate malformed wire input return a domain failure rather than raising transport exceptions.

Update package façades (`domain/__init__.py`, `domain/ports/__init__.py`) to export `CommandEnvelope`, `CommandType`, and `CommandPublisher`, matching the existing export style.

**Implementation record (2026-08-05, Step 4 complete):** `domain/messaging/command_envelope.py` defines `CommandType` (StrEnum: deposit/withdrawal/exchange/transfer) and frozen `CommandEnvelope`; the constructor raises on non-UUID `request_id`, non-`CommandType` type, or naive/non-UTC `submitted_at`, while `CommandEnvelope.try_parse` tolerates raw wire values (strings or typed) and returns `Result.failure(COMMAND_ENVELOPE_INVALID, reason)` for malformed input, unknown types, or naive timestamps — never transport exceptions. New error code `COMMAND_ENVELOPE_INVALID` added to `domain/error_codes.py`. `domain/ports/services/command_publisher.py` defines the `CommandPublisher` protocol (`publish(*, key, envelope)`, returns after broker acknowledgement, raises on bounded failure). Both façades export the new symbols; the existing `ClockService` port remains the single clock source for `submitted_at`. Verified: ruff/mypy pass; construction, valid parse, and all four malformed-input cases behave as specified; grep confirms `domain/` has zero FastAPI/Pydantic/SQLAlchemy/Kafka imports.

## Step 5 — Producer adapter

Create `backend/app/kafka/__init__.py` and `backend/app/kafka/messaging/__init__.py`, then:

Create `backend/app/kafka/messaging/envelope_codec.py` — JSON serialization of `CommandEnvelope` to/from the compact wire shape `{"request_id": "<uuid>", "type": "<type>", "submitted_at": "<RFC 3339>"}`; decoding returns a domain failure for malformed payloads, unknown types, or naive timestamps.

Create `backend/app/kafka/messaging/producer.py`:

```python
from aiokafka import AIOKafkaProducer

from app.domain import CommandEnvelope, CommandPublisher

from .envelope_codec import encode_envelope


class KafkaCommandPublisher(CommandPublisher):
    def __init__(self, producer: AIOKafkaProducer, topic: str) -> None:
        self._producer = producer
        self._topic = topic

    async def publish(self, *, key: str, envelope: CommandEnvelope) -> None:
        if not key:
            raise ValueError("Kafka record key is required")
        await self._producer.send_and_wait(
            self._topic,
            key=key.encode("utf-8"),
            value=encode_envelope(envelope),
        )
```

Build the underlying `AIOKafkaProducer` in `backend/app/kafka/messaging/producer_factory.py` from `KafkaSettings`, mapping the contract settings to client options: `acks="all"`, `enable_idempotence=True`, `request_timeout_ms`, `retry_backoff_ms`, bounded retries, and a delivery bound enforced around `send_and_wait` (e.g. `asyncio.wait_for` with `KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS`). Add safe structured logging (topic, partition, offset, key class — never payloads beyond `request_id`/`type`) on publish success and failure.

Update `backend/app/dependencies.py` with a `build_command_publisher(settings)` factory used by API (Phase 3) and reaper (Phase 5) composition.

**Implementation record (2026-08-05, Step 5 complete):** `app/kafka/` created with a façade plus `messaging/` subpackage: `envelope_codec.py` (compact JSON wire shape `{"request_id","type","submitted_at"}`; `decode_envelope` returns `Result.failure(COMMAND_ENVELOPE_INVALID)` for malformed JSON, non-dict payloads, unknown types, and naive timestamps), `producer.py` (`KafkaCommandPublisher` implementing the `CommandPublisher` port: keyless publish rejected before network I/O; `asyncio.wait_for` enforces the end-to-end delivery bound and raises `PublishTimeoutError`; bounded retry loop honors `KAFKA_PRODUCER_MAX_RETRIES` with exponential backoff capped at `KAFKA_PRODUCER_RETRY_BACKOFF_MAX_MS` using aiokafka's `retriable` error classification; non-retriable errors raise immediately; `start`/`stop` lifecycle delegates), and `producer_factory.py` (`build_aiokafka_producer` maps settings to client options with `acks="all"` and `enable_idempotence=True` hardcoded, SASL/mutual-TLS mapped from settings, `ssl.create_default_context` keeping certificate and hostname verification non-disableable; `build_kafka_command_publisher(settings, *, topic=None)` for command-topic and DLQ reuse). `dependencies.py` exposes `build_command_publisher(settings: KafkaSettings)` for API/reaper composition. Logging is structured via `extra` (topic, partition, offset, key class `admin`/`user`, request_id, command_type — never payloads or raw keys). `pyproject.toml` gained mypy overrides: `follow_untyped_imports` for `aiokafka.*` and scoped `disallow_untyped_calls = false` for `app.kafka.*` (aiokafka's producer methods are unannotated). Verified: ruff/mypy pass; codec round-trip and four malformed-input rejections; keyless publish rejected pre-network; publish bound held at 0.30s against a hanging producer; retriable failure recovered on attempt 3; non-retriable raised on first call. Live broker publication is exercised in Step 8.

## Step 6 — Process shells

Create independently runnable entry points that validate owned settings, construct dependencies, report readiness, handle `SIGINT`/`SIGTERM` gracefully, and exit cleanly — with no wallet execution or republication behavior yet.

Create `backend/app/kafka/worker/__init__.py` and `backend/app/kafka/worker/main.py`:

- validate worker-owned settings (shared DB + logging, Kafka connection/topics/group, producer settings for DLQ, worker execution/liveness);
- verify PostgreSQL connectivity and the expected Alembic revision;
- verify broker connectivity, `wallet`/`wallet_dlq` metadata, and group `wallet_worker`;
- log readiness and idle until shutdown; on signal, stop polling, close consumer/producer/session factory, exit 0.

Create `backend/app/kafka/reaper/__init__.py` and `backend/app/kafka/reaper/main.py` analogously for reaper-owned settings (no consumer group, no DLQ ownership), idling on a `REAPER_INTERVAL_SECONDS` schedule without scanning yet.

Run commands (document them in this file once verified):

```bash
cd backend
uv run python -m app.kafka.worker
uv run python -m app.kafka.reaper
```

## Step 7 — Readiness

Update `backend/app/api/routers/health.py` so `GET /health/ready` checks only API-owned dependencies: PostgreSQL, expected schema revision, Kafka connectivity, and `wallet` topic metadata — returning `503 SERVICE_UNAVAILABLE` when any is unusable. Do not advertise submission readiness while the bounded publication path cannot run.

Worker and reaper shells expose readiness through structured logs and exit codes (no listening port); each checks only its owned dependencies per [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §14.

Add least-privilege deployment guidance as a comment block in `docker-compose.yml` (or `docs/v2/OPERATIONS.md` if a section exists): API and reaper write `wallet`; the worker reads `wallet` and writes `wallet_dlq`; no application process receives broad broker-administration rights; production ACLs are deployment configuration, not application settings.

## Step 8 — Smoke check

Run each check and record the observed result:

1. **Broker and topics:**

```bash
docker compose up -d kafka && docker compose run --rm kafka-init
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic wallet
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic wallet_dlq
```

Confirm `wallet` has 3 partitions, both topics exist with reviewed settings.

2. **Keyed publication and per-key order:** using a short throwaway `uv run python` snippet against the producer adapter, publish several messages with two distinct keys and one message attempt without a key; consume back with `kafka-console-consumer.sh`. Confirm identical keys land on one partition, per-key order holds, and the keyless call is rejected before network I/O.
3. **Process shells:** start `uv run python -m app.kafka.worker` and `uv run python -m app.kafka.reaper`; confirm readiness logs, then `Ctrl+C` and confirm clean shutdown with exit code 0.
4. **Bounded failure:** point the producer at an unreachable broker address and confirm the publish call fails within `KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS` with a structured error.

## Migration and rollback

- Phase 1 changes no financial behavior and no schema; the API keeps serving Version 1 routes unchanged.
- Rollback: `docker compose stop kafka kafka-init`, revert `docker-compose.yml` and `pyproject.toml`/`uv.lock` to the recorded pre-Phase-1 state, and remove the local `kafka_data` volume. Version 1 API behavior is intact throughout.
- Prohibit partition-count changes during rollback or incident response without an ordering-impact review.

## Hard stop gate

- [ ] The smoke check shows explicit topic creation, key placement, per-key order, readiness, and a bounded publish failure surfacing as an error.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy app` pass from `backend/`; dependency review done; `uv.lock` consistent.
- [ ] No wallet route publishes and no worker mutates balances.
- [ ] Broker image and client are pinned; launch commands are documented above.
