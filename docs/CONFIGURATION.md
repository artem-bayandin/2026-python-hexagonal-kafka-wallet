# Configuration contract

## Profiles

`APP_ENV` is mandatory and has one of `development`, `test`, or `production`.
Configuration is validated at application startup; an unknown environment or missing required secret prevents startup.

| Profile | Purpose | Prohibited behavior |
| --- | --- | --- |
| `development` | Local learning and the complete demo scenario. | Do not expose it to untrusted networks. |
| `test` | Automated tests with isolated dependencies. | Do not reuse development or production data or secrets. |
| `production` | Future controlled deployment only. | Demo OTP output, static admin access, and Kafka diagnostics are disabled and cannot be enabled. |

Feature flags default to `false`; a development-only feature requires both `APP_ENV=development` and its explicit flag.

## Backend environment variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `APP_ENV` | Yes | None | `development`, `test`, or `production`. |
| `DATABASE_URL` | Yes | None | Async SQLAlchemy PostgreSQL URL. Never log it. |
| `JWT_SECRET` | Yes | None | At least 32 random bytes; rotate through a controlled key migration. |
| `JWT_ACCESS_TOKEN_TTL_MINUTES` | No | `60` | Positive integer. |
| `OTP_HMAC_SECRET` | Yes | None | Independent from `JWT_SECRET`; at least 32 random bytes. |
| `OTP_TTL_SECONDS` | No | `300` | Positive integer. |
| `OTP_MAX_ATTEMPTS` | No | `5` | Positive integer. |
| `ENABLE_DEMO_OTP` | No | `false` | May be `true` only in development. |
| `ADMIN_API_KEY` | Development only | None | Required with development admin endpoints; never use `x_admin_key` outside local demos. |
| `ENABLE_KAFKA_DIAGNOSTICS` | No | `false` | May be `true` only in development and only in version 2. |
| `KAFKA_BOOTSTRAP_SERVERS` | Version 2 | None | Comma-separated broker addresses. |
| `KAFKA_COMMAND_TOPIC` | No | `wallet.commands.v1` | One partition key per target user ID. |
| `KAFKA_WORKER_GROUP_ID` | No | `wallet-command-worker-v1` | One worker consumer group. |
| `CORS_ALLOWED_ORIGINS` | Yes outside development | None | Comma-separated explicit HTTPS origins; never `*` with credentials. |
| `LOG_LEVEL` | No | `INFO` | Structured logs must redact secrets. |

## Frontend environment variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `VITE_API_BASE_URL` | Yes | None | Public API origin without a trailing slash. |
| `VITE_OPERATION_POLL_INITIAL_MS` | No | `2000` | Version-2 operation polling initial delay. |
| `VITE_OPERATION_POLL_MAX_MS` | No | `10000` | Exponential backoff ceiling. |

The frontend must not receive `JWT_SECRET`, `OTP_HMAC_SECRET`, `ADMIN_API_KEY`, database URLs, or Kafka credentials. `VITE_*` values are public build-time values.

## Local endpoints and containers

The initial local defaults are:

| Service | Address |
| --- | --- |
| FastAPI | `http://127.0.0.1:8000` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| React development server | `http://127.0.0.1:5173` |
| PostgreSQL | `127.0.0.1:5432` |
| Kafka | Internal Compose network by default; do not expose a host port unless required for local debugging. |

The actual Compose file must pin container image tags and use named volumes.
The [backend `.env.example`](../backend/.env.example) contains only development-safe placeholders, never real credentials.

## Secrets and rotation

- Use a secret manager in production; `backend/.env` is local-development only and is gitignored.
- Generate separate high-entropy values for JWT signing and OTP HMAC.
- Rotate a JWT key by accepting a bounded set of active key IDs during the transition, issuing only with the new key, then retiring the old key after all tokens expire.
- Rotate OTP HMAC material by invalidating outstanding challenges if dual-verification is not implemented.
- Redact all secret values, JWTs, OTPs, and database/Kafka connection strings from logs, traces, error responses, and diagnostics records.
