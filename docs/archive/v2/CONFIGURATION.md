# Version 2 configuration contract

## 1. Purpose and authority

This document is the canonical configuration contract for Version 2 of the Clean Architecture Wallet. It inherits the Version 1 settings from the [Version 1 configuration contract](../v1/CONFIGURATION.md) and adds the Kafka producer, command worker, stale-submitted reaper, Server-Sent Events (SSE), and admin long-poll settings required by the [Version 2 design](README.md), [technical requirements](TECHNICAL_REQUIREMENTS.md), and [HTTP and SSE API contract](API_CONTRACT.md).

Configuration names in this document are the public deployment interface. Implementations may group or map them internally, but must not silently introduce different environment names, weaker defaults, or profile-dependent behavior that contradicts this contract.

## 2. Profiles and loading

`APP_ENV` is mandatory and must be exactly `development`, `test`, or `production`. Every API, worker, and reaper process validates its owned settings before becoming ready; unknown variables may be rejected, and an unknown profile, malformed value, missing required setting, forbidden development shortcut, or violated cross-setting invariant prevents startup.

| Profile | Purpose | Required behavior |
| --- | --- | --- |
| `development` | Local learning and the complete demo scenario. | Development-only demo OTP output and static admin-key access may be enabled explicitly; plaintext local PostgreSQL and Kafka connections are allowed only on trusted local networks. |
| `test` | Reserved for future automated tests with isolated dependencies; unused in the current delivery (see [TECHNICAL_REQUIREMENTS.md](TECHNICAL_REQUIREMENTS.md) §15). | When automated tests are introduced, they must use dedicated databases, Kafka topics or broker instances, consumer groups, and secrets; development or production data and credentials must never be reused. |
| `production` | Controlled deployment only. | Demo OTP output and static admin-key access are forbidden; TLS, authenticated Kafka access, explicit CORS origins, externally managed secrets, and a production admin-authorization replacement are required. |

Environment variables are process inputs. A local `.env` file may be used only for development and test tooling, must remain gitignored, and must not be copied into an image. Empty strings are treated as missing values unless a variable explicitly permits an empty value.

## 3. Shared backend variables

These inherited settings apply to every backend process that uses the corresponding dependency. `Required` describes the configuration contract; a process may omit a setting it does not own according to [process ownership](#10-process-ownership).

| Variable | Required | Default | Validation and meaning |
| --- | --- | --- | --- |
| `APP_ENV` | Yes | None | Exactly `development`, `test`, or `production`. |
| `DATABASE_URL` | API, worker, reaper | None | Async SQLAlchemy PostgreSQL URL. It must identify an isolated test database in `test`, use TLS in production, and never be logged. |
| `JWT_SECRET` | API | None | High-entropy signing secret of at least 32 random bytes, independent from every other secret. |
| `JWT_ACCESS_TOKEN_TTL_MINUTES` | API | `60` | Positive integer. |
| `OTP_HMAC_SECRET` | API | None | High-entropy HMAC secret of at least 32 random bytes, distinct from `JWT_SECRET`. |
| `OTP_TTL_SECONDS` | API | `300` | Positive integer. |
| `OTP_MAX_ATTEMPTS` | API | `5` | Positive integer. |
| `ENABLE_DEMO_OTP` | API | `false` | Boolean; may be `true` only when `APP_ENV=development`. |
| `ADMIN_API_KEY` | Development API only | None | Required when development admin routes are enabled. It is forbidden in production and is not a production authorization mechanism. |
| `CORS_ALLOWED_ORIGINS` | API; required outside development | None | Comma-separated explicit origins without paths or trailing slashes. Production origins must use HTTPS; `*` is forbidden when credentials or authorization headers are accepted. |
| `LOG_LEVEL` | API, worker, reaper | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`; changing verbosity must not disable redaction. |

Production deployment must not expose admin routes until static `X-Admin-Key` access has been replaced by an approved production authorization mechanism. That replacement may add its own reviewed settings, but must not reinterpret `ADMIN_API_KEY` as production-safe.

## 4. Kafka connection and topic contract

The API producer, worker, and reaper use the same command topic identity and compatible broker-security settings. Local development defaults are `wallet`, `wallet_dlq`, and `wallet_worker`; all three are overridable through environment variables provided every process in a deployment uses matching values and the broker provisions the configured topic names.

| Variable | Required | Default | Validation and meaning |
| --- | --- | --- | --- |
| `KAFKA_BOOTSTRAP_SERVERS` | API, worker, reaper | None | Non-empty comma-separated broker endpoints. Local Compose uses `kafka:9092`; production must provide multiple bootstrap endpoints when the broker topology supports them. |
| `KAFKA_COMMAND_TOPIC` | API, worker, reaper | `wallet` | Non-empty topic name for wallet commands. User commands are keyed by submitting user UUID; admin deposits use the literal key `admin`. |
| `KAFKA_DLQ_TOPIC` | Worker | `wallet_dlq` | Non-empty dead-letter topic; must not equal the command topic. |
| `KAFKA_WORKER_GROUP_ID` | Worker | `wallet_worker` | Non-empty consumer group id. Every command-worker replica in one deployment joins this group. |
| `KAFKA_SECURITY_PROTOCOL` | API, worker, reaper | `PLAINTEXT` | One of `PLAINTEXT`, `SSL`, `SASL_PLAINTEXT`, or `SASL_SSL`. Production requires `SSL` or `SASL_SSL`; plaintext modes are local/test only. |
| `KAFKA_SASL_MECHANISM` | When SASL is selected | None | Deployment-approved mechanism supported by the selected broker and client. |
| `KAFKA_SASL_USERNAME` | When SASL is selected | None | Secret credential; must be paired with `KAFKA_SASL_PASSWORD`. |
| `KAFKA_SASL_PASSWORD` | When SASL is selected | None | Secret credential; must be paired with `KAFKA_SASL_USERNAME`. |
| `KAFKA_SSL_CA_FILE` | Production TLS | None | Readable CA bundle used to verify broker certificates. |
| `KAFKA_SSL_CERT_FILE` | When mutual TLS is selected | None | Readable client certificate; must be paired with `KAFKA_SSL_KEY_FILE`. |
| `KAFKA_SSL_KEY_FILE` | When mutual TLS is selected | None | Readable private key; must be paired with `KAFKA_SSL_CERT_FILE` and must be secret-mounted. |

TLS certificate verification and broker hostname verification are mandatory in production and are not disableable settings. SASL credentials and mutual-TLS identities should be distinct by role so ACLs can grant the API and reaper write access to the command topic, the worker read access to the command topic and write access to the DLQ topic, and no application process broad broker-administration rights.

## 5. Producer reliability settings

These settings are shared by the API command publisher, reaper republisher, and worker DLQ publisher. Names express application semantics rather than a particular Kafka client option; the adapter must map them to equivalent client controls and the effective behavior must be confirmed during the smoke verification.

| Variable | Required | Default | Validation and meaning |
| --- | --- | --- | --- |
| `KAFKA_PRODUCER_REQUEST_TIMEOUT_MS` | No | `10000` | Positive broker-request timeout; also the consumer request timeout. |
| `KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS` | No | `30000` | Positive end-to-end bound for one publish call (`asyncio.wait_for` around `send_and_wait`); must be at least the request timeout. |
| `KAFKA_PRODUCER_RETRY_BACKOFF_MS` | No | `200` | Fixed delay between aiokafka inner produce (and consumer fetch) retries. |

All producers always use `acks=all` and Kafka producer idempotence; these guarantees are fixed and are not feature flags. Publication returns success only after broker acknowledgement and fails within `KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS`. Inner produce retries are time-based inside aiokafka; idempotent mode does not expire batches on the request timeout, so the delivery bound is required.

## 6. Worker consumption and execution

Each consumed command is executed once per delivery. There is no in-process attempt budget and no persisted attempts counter. A retryable infrastructure failure on that single execute follows the same terminal DB + DLQ + ACK path as poison.

| Variable | Required | Default | Validation and meaning |
| --- | --- | --- | --- |
| `WORKER_RETRY_BACKOFF_MS` | Worker | `500` | Positive delay used as the submitted-row visibility wait (not an execution retry schedule). |
| `WORKER_POLL_TIMEOUT_MS` | Worker | `1000` | Positive maximum wait for a poll to return work or control to shutdown handling. |
| `WORKER_HEARTBEAT_INTERVAL_MS` | Worker | `3000` | Positive consumer heartbeat interval. |
| `WORKER_SESSION_TIMEOUT_MS` | Worker | `30000` | Positive broker session timeout and greater than the heartbeat interval. |
| `WORKER_MAX_POLL_INTERVAL_MS` | Worker | `300000` | Positive maximum interval permitted between consumer polls. |

The worker adapter must map polling, heartbeat, session, and maximum-poll settings to the selected client without exposing client-specific option names as additional public configuration. `WORKER_HEARTBEAT_INTERVAL_MS` must be comfortably below `WORKER_SESSION_TIMEOUT_MS`, and `WORKER_MAX_POLL_INTERVAL_MS` must exceed the worst-case time between polls, including command execution, database timeouts, and DLQ acknowledgement. Offsets are committed only after a dispatch ACK (`enable_auto_commit=false`). The worker must continue heartbeats when the client supports it, must not hold a PostgreSQL transaction during Kafka waits, and must leave the original record unacknowledged if terminal-state or DLQ durability has not completed.

## 7. Reaper settings

The reaper scans only stale `submitted` rows, republishes the original command key and envelope, and guards `submitted → pending` after acknowledgement. It never republishes stale `pending` or `in_progress` rows.

| Variable | Required | Default | Validation and meaning |
| --- | --- | --- | --- |
| `REAPER_INTERVAL_SECONDS` | Reaper | `30` | Positive delay between completed scans. |
| `REAPER_STALE_THRESHOLD_SECONDS` | Reaper | `60` | Positive minimum age of a `submitted` row before it is eligible for claiming and republication. |
| `REAPER_BATCH_SIZE` | Reaper | `100` | Integer from `1` through `1000`; maximum rows claimed in one scan. |

`REAPER_STALE_THRESHOLD_SECONDS` must exceed the configured producer delivery bound plus expected database commit and scheduling jitter so the reaper does not race a normally completing API publish. Scans must use the indexed status and age fields, bounded batches, and concurrency-safe claiming or guarded updates; multiple reaper instances must not produce an avoidable republish storm.

## 8. HTTP streaming and long polling

| Variable | Required | Default | Validation and meaning |
| --- | --- | --- | --- |
| `ADMIN_LONG_POLL_DEFAULT_SECONDS` | API | `25` | Integer from `0` through `ADMIN_LONG_POLL_MAX_SECONDS`; used when `timeout_seconds` is omitted. |
| `ADMIN_LONG_POLL_MAX_SECONDS` | API | `30` | Positive integer and the inclusive maximum accepted `timeout_seconds`; `0` remains valid per request to disable waiting. |
| `SSE_HEARTBEAT_INTERVAL_SECONDS` | API | `15` | Positive interval for sending an SSE comment such as `: keep-alive` while no application event is available. |
| `SSE_RETRY_MILLISECONDS` | API | `3000` | Integer of at least `3000`; the server may emit this SSE `retry` value as reconnect guidance. |
| `TRANSACTION_STATUS_CHANNEL` | API, worker | `transaction_status_changed` | PostgreSQL `LISTEN`/`NOTIFY` channel name; API listeners and worker/API emitters must use the same value. |
| `STATUS_EVENT_PAGE_SIZE` | API | `100` | Integer from `1` through `1000`; maximum status-event rows fetched per catch-up page. |

Admin long polling remains a PostgreSQL query over the `(updated_at, id)` cursor and never reads Kafka. SSE heartbeats carry no application meaning, must not advance the event cursor, and should be shorter than the idle timeout of every trusted reverse proxy or load balancer. The server may close a stream at any time; reconnect remains at least once, uses `Last-Event-ID`, and requires a database-backed snapshot reconciliation as defined by the API contract.

Reverse proxies must disable buffering and response compression for `GET /me/stream`, permit connections longer than `SSE_HEARTBEAT_INTERVAL_SECONDS`, forward `Last-Event-ID`, and avoid caching SSE responses. Proxy idle and request timeouts are deployment settings rather than application environment variables, but deployment validation must confirm they are compatible with the heartbeat interval and the configured admin long-poll maximum.

## 9. Frontend variables

| Variable | Required | Default | Validation and meaning |
| --- | --- | --- | --- |
| `VITE_API_BASE_URL` | Frontend build | None | Public API origin without a trailing slash. Production must use HTTPS, and its origin must be allowed by `CORS_ALLOWED_ORIGINS`. |
| `VITE_STATUS_TOAST_MS` | Frontend build | `5000` | Positive milliseconds to show a status toast before auto-hide. |

Every `VITE_*` value is public build-time data. The frontend must never receive database or Kafka URLs, JWT or OTP secrets, admin credentials, TLS private keys, SASL credentials, or server timeout controls.

## 10. Process ownership

| Process | Owns and validates |
| --- | --- |
| API | Shared database, authentication, CORS and logging settings; Kafka connection and command-topic settings; producer settings; admin long-poll settings; SSE settings; `TRANSACTION_STATUS_CHANNEL` and `STATUS_EVENT_PAGE_SIZE`. |
| Worker | Shared database and logging settings; Kafka connection, command-topic, DLQ-topic and worker-group settings; producer settings for DLQ publication; worker execution and consumer-liveness settings; `TRANSACTION_STATUS_CHANNEL` (NOTIFY emit). |
| Reaper | Shared database and logging settings; Kafka connection and command-topic settings; producer settings; reaper schedule, staleness, and batch settings. |
| Frontend build | `VITE_API_BASE_URL` and `VITE_STATUS_TOAST_MS`. |
| Topic bootstrap or deployment tooling | Topic names plus partition, replication, retention, TLS, authentication, and ACL policy; application processes do not auto-create production topics. |

Settings shared by processes must resolve to compatible values in one deployment. The worker does not own HTTP, SSE, CORS, JWT, OTP, or admin settings; the reaper does not own consumer-group, DLQ, worker-retry, HTTP, or authentication settings; the API does not consume from `wallet`.

## 11. Topic provisioning

Local bootstrap creates `wallet` and `wallet_dlq` before application readiness, with `wallet` using three partitions by default and a replication factor of one for a single local broker. Production deployment must declare partition count, replication factor, retention, cleanup policy, minimum in-sync replicas, and ACLs in infrastructure configuration; those controls are intentionally not application runtime environment variables.

The `wallet` partition count may differ by environment, but production changes require review because increasing it changes future key-to-partition mapping and can interrupt continuity of per-key ordering across the change. `wallet_dlq` retention must be long enough for alerting, investigation, and controlled replay. Both topics use durable retention appropriate to their role and must not rely on broker auto-creation defaults.

## 12. Local service topology

| Service or process | Local address | Network and ownership |
| --- | --- | --- |
| React development server | `http://127.0.0.1:5173` | Host-facing development UI; uses `VITE_API_BASE_URL=http://127.0.0.1:8000`. |
| FastAPI and Swagger UI | `http://127.0.0.1:8000`, `http://127.0.0.1:8000/docs` | Host-facing development API; connects to PostgreSQL and Kafka on the Compose network. |
| PostgreSQL | `127.0.0.1:5432` from the host; `postgres:5432` in Compose | Named persistent volume; isolated credentials and database per environment. |
| Kafka | `kafka:9092` in Compose | Internal by default. An optional host listener such as `127.0.0.1:29092` may be added only for explicit local broker debugging. |
| Command worker | No listening port | Independent process connected to PostgreSQL and Kafka; joins `wallet_worker`. |
| Reaper | No listening port | Independent process or scheduled task connected to PostgreSQL and Kafka. |

Compose must pin exact container image tags or immutable digests, use health checks and named volumes where state is retained, and start API, worker, and reaper readiness only after their required dependencies and topic configuration are available. Kafka must not be bound to a public interface by default.

## 13. Secrets, TLS, and deployment controls

- Use a secret manager or equivalent runtime secret injection in production; never bake secrets into images, frontend assets, Compose files, source code, or committed environment files.
- Generate independent high-entropy values for JWT signing, OTP HMAC, database credentials, Kafka SASL credentials, and TLS private keys; role identities must use least-privilege database grants and Kafka ACLs.
- Rotate JWT signing keys through a controlled compatibility window, issuing only with the new key and retiring the old key after prior tokens expire; rotate OTP HMAC material by invalidating outstanding challenges unless dual verification is deliberately implemented.
- Rotate database, Kafka, and TLS credentials without granting broader access. Certificate expiry, secret age, failed authentication, and authorization denials must be observable without logging credential material.
- Require HTTPS at the public API and frontend boundary, TLS for production PostgreSQL, and verified TLS plus authentication for production Kafka. Terminating public TLS at a trusted proxy is acceptable only when the remaining network path is protected according to the deployment threat model.
- Redact secret values, JWTs, OTPs, admin keys, database and Kafka URLs, SASL credentials, private-key material, and raw unexpected exceptions from logs, metrics, traces, DLQ context, SSE events, HTTP errors, and health responses.

## 14. Validation invariants

In addition to per-variable validation, startup and deployment checks enforce all of the following:

- `KAFKA_COMMAND_TOPIC`, `KAFKA_DLQ_TOPIC`, and `KAFKA_WORKER_GROUP_ID` are non-empty; the command and DLQ topics are distinct.
- Every wallet command has a non-empty key: submitting user UUID for user operations and the literal `admin` for deposits.
- Producer acknowledgement is `all`, producer idempotence is enabled, inner retries use `KAFKA_PRODUCER_RETRY_BACKOFF_MS`, and delivery timeout is not shorter than request timeout.
- Heartbeat is shorter than session timeout; maximum poll interval covers polling plus the bounded DLQ publication wait.
- Reaper interval, stale threshold, and batch size are positive and bounded; stale threshold exceeds the producer delivery bound plus operational jitter.
- Admin default long-poll duration does not exceed `ADMIN_LONG_POLL_MAX_SECONDS`; SSE retry guidance is at least three seconds; SSE heartbeat is compatible with deployed proxy idle timeouts.
- `ENABLE_DEMO_OTP=true` and `ADMIN_API_KEY` are accepted only in development; production requires explicit HTTPS CORS origins and rejects static admin access.
- Production database and Kafka connections use authenticated, certificate-verified encryption; paired SASL or mutual-TLS fields are complete and readable.
- Any future test resources must be isolated from development and production, and no process becomes ready until its database schema, broker connection, required topics, and role permissions are valid.

There are no configuration variables for client-side operation polling, a transactional outbox, or Kafka diagnostics. Those mechanisms are outside the Version 2 contract.
