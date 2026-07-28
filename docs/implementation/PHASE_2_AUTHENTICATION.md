# Phase 2 — Authentication

Complete Slice 0 configuration first, then implement email OTP authentication end to end in four vertical feature slices, in this exact order:

1. `request-otp`
2. `verify-otp`
3. `healthcheck`
4. `logout`

Within each feature slice, work in the strict order **API → Domain → DB → UI**. Do not run or demonstrate a feature slice until all four sections in that slice are complete.

Canonical behavior is defined by [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md), [API_CONTRACT.md](../API_CONTRACT.md), [CONFIGURATION.md](../CONFIGURATION.md), and [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md). Those documents and this guide are aligned on the phase-specific scope below.

## Scope

This phase includes OTP request and verification, Bearer access tokens, server-side authentication sessions, authenticated health, logout, and the minimal React login/authenticated state.

This phase deliberately excludes:

- wallet `accounts`; add them in roadmap **Step 4 — Model accounts, balances, and transactions**;
- automated tests; complete the deferred authentication unit tests from roadmap Steps 3, 6, and 7 together with the integration coverage in **Step 11 — Complete version-1 integration coverage**;
- HTTP idempotency; it is deferred entirely to the roadmap's final optional hardening phase.

Use manual verification and the static quality checks in this guide. Do not add test files during this phase.

## Done when

A browser can request a development demo OTP, verify it, show **Authorized**, survive a reload by validating the token against `GET /health/authenticated`, and log out only the current session. Reloading during OTP entry returns to the email form because the OTP step exists only in React memory. Missing, malformed, expired, or revoked credentials always produce the standard `401` error envelope. Backend ruff/mypy and frontend lint/typecheck pass.

## Architecture rules

- `backend/app/domain/` imports only Python standard-library modules and other domain models or `Protocol` ports.
- Domain handlers never import FastAPI, Pydantic, SQLAlchemy, PyJWT, `app.auth`, or `app.db`.
- Every command and query handler returns the immutable generic `Result[T]` from `backend/app/domain/result.py`.
- `CurrentUser` is an immutable domain value; `CurrentUserProvider` is a domain port implemented by the API with request-scoped state.
- `backend/app/domain/ports/services.py` owns `ClockService`, `OtpService`, and `TokenService`.
- SQLAlchemy repositories live under `backend/app/db/` and structurally implement domain ports.
- HMAC/`secrets` and PyJWT implementations live under `backend/app/auth/` and structurally implement domain ports.
- `backend/app/dependencies.py` is the composition root. It opens SQLAlchemy transaction contexts, composes handlers with repositories sharing one session, invokes the handler, and returns its `Result`.
- API routers translate HTTP DTOs to commands and successful result data to response DTOs. Result-error-code-to-HTTP mapping lives only in `backend/app/api/exception_handlers.py`.
- Every command executes inside `AsyncSession.begin()`. A returned `Result`, whether successful or failed, exits normally and commits; an unexpected exception escapes and rolls back.

## Shared design targets

This section is reference material, not an implementation stage. It contains no create/update step. All implementation instructions appear only in Slice 0–4 at the point they are executed, preserving the API → Domain → DB → UI order.

### Target layout

Use this final target layout as a reference only:

```text
backend/
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
└── app/
    ├── config.py
    ├── dependencies.py
    ├── main.py
    ├── api/
    │   ├── current_user_provider.py
    │   ├── dependencies.py
    │   ├── exception_handlers.py
    │   ├── result_mapping.py
    │   ├── routers/
    │   │   ├── auth.py
    │   │   └── health.py
    │   └── schemas/
    │       ├── auth.py
    │       └── errors.py
    ├── auth/
    │   ├── jwt_service.py
    │   └── otp_service.py
    ├── db/
    │   ├── mappers.py
    │   ├── models.py
    │   ├── session.py
    │   └── repositories/
    │       ├── auth_repository.py
    │       └── user_repository.py
    └── domain/
        ├── current_user.py
        ├── error_codes.py
        ├── result.py
        ├── token_claims.py
        ├── entities/
        │   ├── auth_session.py
        │   ├── otp_challenge.py
        │   └── user.py
        ├── ports/
        │   ├── command_repositories.py
        │   ├── current_user_provider.py
        │   ├── query_repositories.py
        │   └── services.py
        └── use_cases/
            ├── commands/
            │   ├── logout.py
            │   ├── request_otp.py
            │   └── verify_otp.py
            └── queries/
                └── get_current_user.py
```

### Shared domain targets

The final framework-free domain model for this phase contains:

- `User(id: UUID, email: str, created_at: datetime)`;
- `OtpChallenge(id: UUID, user_id: UUID, otp_digest: str, expires_at: datetime, failed_attempt_count: int, consumed_at: datetime | None, invalidated_at: datetime | None, created_at: datetime)`;
- `AuthSession(jti: UUID, user_id: UUID, expires_at: datetime, revoked_at: datetime | None, created_at: datetime)`;
- `TokenClaims(user_id: UUID, session_jti: UUID, expires_at: datetime)`;
- frozen `CurrentUser(id: UUID, email: str, session_jti: UUID)`.

The final stable error-code set is `OTP_INVALID`, `OTP_EXPIRED`, `OTP_LOCKED`, `OTP_CONSUMED`, `OTP_SUPERSEDED`, and `AUTHENTICATION_FAILED`.

The immutable generic `Result[T]` target has these factories and read-only properties:

- `Result.success(data: T | None = None)`;
- `Result.failure(error_code: str, reason: Exception | None = None)`;
- `is_success: bool`;
- `data: T | None`;
- `error_code: str | None`;
- `reason: Exception | None`.

`Result[T]` is a frozen, slotted dataclass. Its `__post_init__` rejects invalid states with `ValueError("Invalid Result initialization.")`: success has no error code or reason; failure has a non-empty error code and no data. `reason` is internal diagnostic context and is never serialized, exposed to clients, or logged automatically.

Every command and query returns `Result[T]`. Expected OTP and authentication outcomes return `Result.failure`; unexpected infrastructure and programming failures remain exceptions so the SQLAlchemy transaction context rolls back.

The final structural service-port surface is:

- `ClockService.now() -> datetime`; implementations must return timezone-aware UTC;
- `OtpService.generate_code() -> str`;
- `OtpService.digest(normalized_email: str, code: str) -> str`;
- `OtpService.matches(normalized_email: str, code: str, expected_digest: str) -> bool`;
- `TokenService.encode(user_id: UUID, session_jti: UUID, expires_at: datetime) -> str`;
- `TokenService.decode(token: str) -> Result[TokenClaims]`.

Repository ports are separated into command and query surfaces. Handlers receive those ports directly, and the domain contains no adapter behavior.

### Shared transaction target

The transaction target is one `AsyncSession.begin()` context per command. Every repository used by that command shares the session. Domain handlers never call `commit()` or `rollback()`: a returned `Result`, including a failed result, exits normally and commits intentional changes, while an unexpected exception escapes and triggers automatic rollback.

### Shared database target

The authentication schema target contains only `users`, `otp_challenges`, and `auth_sessions`.

```text
users
  id UUID PRIMARY KEY
  email VARCHAR(320) UNIQUE NOT NULL
  created_at TIMESTAMPTZ NOT NULL

otp_challenges
  id UUID PRIMARY KEY
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT
  otp_digest VARCHAR(64) NOT NULL
  expires_at TIMESTAMPTZ NOT NULL
  failed_attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempt_count >= 0)
  consumed_at TIMESTAMPTZ NULL
  invalidated_at TIMESTAMPTZ NULL
  created_at TIMESTAMPTZ NOT NULL

auth_sessions
  jti UUID PRIMARY KEY
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT
  expires_at TIMESTAMPTZ NOT NULL
  revoked_at TIMESTAMPTZ NULL
  created_at TIMESTAMPTZ NOT NULL
```

The required indexes include `otp_challenges(user_id, created_at DESC)`, `auth_sessions(user_id)`, and this partial unique index:

```sql
CREATE UNIQUE INDEX uq_otp_challenges_one_current_per_user
ON otp_challenges (user_id)
WHERE consumed_at IS NULL AND invalidated_at IS NULL;
```

“Current” deliberately ignores expiry and failed-attempt count. An expired or locked challenge remains current until it is consumed or invalidated, so request and verification can classify it correctly. The partial index guarantees at most one current row per user.

### Shared API error targets

The final `ErrorEnvelope` schema target is:

```python
from typing import Any

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
```

The final API result-mapping target consists of:

- `ApiResultError(error_code: str)`, an API-layer exception carrying only the error code;
- `unwrap_result(result: Result[T]) -> T`, which returns `data` for success and raises `ApiResultError` for failure; `T` is `None` for no-content commands such as logout.

`unwrap_result` never copies, exposes, or logs `Result.reason`. It runs only after a transactional command executor returns, so the transaction is already committed before a failed result becomes an API-layer exception.

`backend/app/api/exception_handlers.py` is the only result-error-code-to-HTTP mapping. It maps `ApiResultError.error_code` to the status and safe message below. An unknown error code becomes `500 INTERNAL_ERROR` without exposing the unknown value to the client.

| Outcome | Status | Code |
| --- | --- | --- |
| request validation | `422` | `VALIDATION_ERROR` |
| failed result | `422` | `OTP_INVALID` |
| failed result | `422` | `OTP_EXPIRED` |
| failed result | `422` | `OTP_LOCKED` |
| failed result | `422` | `OTP_CONSUMED` |
| failed result | `422` | `OTP_SUPERSEDED` |
| failed result | `401` | `AUTHENTICATION_FAILED` |
| unmapped result code or uncaught exception | `500` | `INTERNAL_ERROR` |

Every handled response, including every `401`, is an `ErrorEnvelope`. Safe messages come from the central error-code mapping, never from `Result.reason`. FastAPI's default non-envelope authentication response is not part of the target behavior.

`unwrap_result` does not select successful status codes. Routes retain their explicit `201` request-OTP, `200` verify/health, and `204` logout statuses. Request validation remains `422 VALIDATION_ERROR`, and uncaught exceptions remain `500 INTERNAL_ERROR`.

## Slice 0 — configuration

Complete this preparation before Slice 1. Change only the existing configuration files named below; do not create any directories or other files from the target layout yet.

Extend `backend/.env.example` and the gitignored `backend/.env`:

```dotenv
JWT_ACCESS_TOKEN_TTL_MINUTES=60
OTP_TTL_SECONDS=300
OTP_MAX_ATTEMPTS=5
ENABLE_DEMO_OTP=false
```

Update `backend/app/config.py` with these contracts:

- `AppEnv` is a `StrEnum` containing only `development`, `test`, and `production`; `Settings.app_env` uses that enum.
- `jwt_access_token_ttl_minutes`, `otp_ttl_seconds`, and `otp_max_attempts` are integers declared with `Field(gt=0)`.
- `jwt_secret` and `otp_hmac_secret` are `SecretStr`; startup validation requires each UTF-8 value to contain at least 32 bytes and requires the two values to differ.
- `enable_demo_otp` defaults to `False` and may be true only when `app_env is AppEnv.DEVELOPMENT`.
- `cors_allowed_origins` is parsed into a non-empty list of explicit origins. Reject `*` in every profile. Outside development, reject HTTP origins and require every origin to use `https://`.
- Do not log settings or secret values.

## Slice 1 — request-otp

### API

Now create `backend/app/api/schemas/errors.py` with the `ErrorEnvelope` target defined above.

Create `backend/app/api/result_mapping.py` with `ApiResultError` and `unwrap_result`. Create `backend/app/api/exception_handlers.py` with the `422 VALIDATION_ERROR` mapping and the safe `500 INTERNAL_ERROR` fallback for uncaught exceptions or unmapped result codes.

Add these Pydantic DTOs to `backend/app/api/schemas/auth.py`:

```python
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RequestOtpRequest(BaseModel):
    email: EmailStr


class RequestOtpResponse(BaseModel):
    expires_at: datetime
    otp: str | None = Field(default=None)
```

Add `POST /auth/otp/request` to `backend/app/api/routers/auth.py`:

- status is `201 Created`;
- no Bearer credential is required;
- map `RequestOtpRequest.email` to `RequestOtpCommand`;
- invoke the transactional command executor and unwrap its successful `RequestOtpData`;
- return its timezone-aware `datetime` directly;
- declare `response_model=RequestOtpResponse` and `response_model_exclude_none=True`.

The last setting is mandatory: when demo output is disabled, `otp` is omitted rather than serialized as `null`. Never log request-OTP response bodies.

### Domain

Now create:

- `backend/app/domain/result.py` with the complete generic `Result[T]` contract defined above;
- `backend/app/domain/entities/user.py` with `User`;
- `backend/app/domain/entities/otp_challenge.py` with `OtpChallenge`;
- `backend/app/domain/ports/services.py` with `ClockService` and `OtpService`;
- `backend/app/domain/ports/command_repositories.py` with the user and OTP-challenge repository Protocols used below.

Add `RequestOtpCommand(email: str)` and `RequestOtpData(expires_at: datetime, demo_otp: str | None)` to `backend/app/domain/use_cases/commands/request_otp.py`.

Repository contracts used by this handler:

- `UserCommandRepository.ensure_by_email(email, user_id, created_at) -> None`;
- `UserCommandRepository.get_by_email_for_update(email) -> User`;
- `OtpChallengeCommandRepository.invalidate_current_for_user(user_id, invalidated_at) -> int`;
- `OtpChallengeCommandRepository.add(challenge) -> None`.

Normalize email once with `email.strip().casefold()`. The handler algorithm is exact:

```python
async def handle(self, command: RequestOtpCommand) -> Result[RequestOtpData]:
    email = command.email.strip().casefold()
    now = self._clock.now()
    proposed_user_id = uuid4()

    await self._users.ensure_by_email(email, proposed_user_id, now)
    user = await self._users.get_by_email_for_update(email)

    await self._otp_challenges.invalidate_current_for_user(user.id, now)

    code = self._otp.generate_code()
    expires_at = now + timedelta(seconds=self._otp_ttl_seconds)
    await self._otp_challenges.add(
        OtpChallenge(
            id=uuid4(),
            user_id=user.id,
            otp_digest=self._otp.digest(email, code),
            expires_at=expires_at,
            failed_attempt_count=0,
            consumed_at=None,
            invalidated_at=None,
            created_at=now,
        )
    )

    return Result.success(
        RequestOtpData(
            expires_at=expires_at,
            demo_otp=code if self._include_demo_otp else None,
        )
    )
```

Imports for this module come only from `dataclasses`, `datetime`, `uuid`, domain entities, `Result`, and domain ports. The constructor receives `UserCommandRepository`, `OtpChallengeCommandRepository`, `OtpService`, `ClockService`, `otp_ttl_seconds`, and `include_demo_otp`.

### DB

Now create the SQLAlchemy session factory in `backend/app/db/session.py`. Create the three authentication ORM models matching the shared database target in `backend/app/db/models.py`. The first authentication migration includes all three tables; this slice uses only the user and OTP-challenge behavior.

Create the `User` and `OtpChallenge` domain/ORM mappers needed by this slice in `backend/app/db/mappers.py`.

Add the two non-unique indexes and the partial unique OTP index from the shared database target to the ORM metadata and migration.

Implement `backend/app/db/repositories/user_repository.py`:

1. `ensure_by_email` executes `INSERT INTO users (id, email, created_at) VALUES (:id, :email, :created_at) ON CONFLICT (email) DO NOTHING`.
2. `get_by_email_for_update` selects the complete `UserModel` where `email = :email` and applies `FOR UPDATE`.
3. The insert and select run in the same transaction. If another request is creating the same email, PostgreSQL waits for that insert to resolve; the subsequent row lock serializes challenge changes for that user.

Implement `OtpChallengeRepository` in `backend/app/db/repositories/auth_repository.py`:

- `invalidate_current_for_user` updates **all** rows for the user where both `consumed_at IS NULL` and `invalidated_at IS NULL`; do not filter by expiry or attempt count;
- execute the invalidation as an explicit SQL `UPDATE` before adding the replacement row, so the partial unique predicate is cleared first;
- `add` maps the domain entity to an ORM model and adds it to the session.

This lock order is mandatory for every OTP request: atomic user insert, lock user, execute the current-challenge invalidation, insert the new challenge, then return from the handler so the transaction context commits. The user lock plus partial unique index makes concurrent requests deterministic and prevents two current challenges.

Alembic belongs under `backend/` in this repository. Initialize it now:

```sh
cd backend
uv run alembic init alembic
```

Configure `backend/alembic/env.py` to import `Base` from `app.db.models`, set `target_metadata = Base.metadata`, use the async migration pattern, and obtain the URL from `get_settings().database_url`. Keep `backend/alembic.ini` beside `pyproject.toml`.

Generate, review, and apply the migration:

```sh
cd backend
uv run alembic revision --autogenerate -m "add authentication tables"
uv run alembic upgrade head
```

Confirm the generated revision contains the partial unique index with the exact predicate above. If autogenerate omits the predicate, add an `op.create_index` call named `uq_otp_challenges_one_current_per_user`, over `["user_id"]`, with `unique=True` and `postgresql_where=sa.text("consumed_at IS NULL AND invalidated_at IS NULL")`.

Now add the request-OTP transactional executor to `backend/app/dependencies.py`:

```python
async def execute_request_otp(
    request: Request,
    command: RequestOtpCommand,
) -> Result[RequestOtpData]:
    async with request.app.state.session_factory() as session:
        async with session.begin():
            handler = build_request_otp_handler(
                session,
                request.app.state.settings,
            )
            return await handler.handle(command)
```

Compose `SystemClock`, `HmacOtpService`, `UserRepository`, `OtpChallengeRepository`, and `RequestOtpHandler` inside that session. Enable the handler's demo OTP output only when both conditions are true:

```python
include_demo_otp = (
    settings.app_env is AppEnv.DEVELOPMENT and settings.enable_demo_otp
)
```

`HmacOtpService` in `backend/app/auth/otp_service.py` must:

- generate exactly six digits with `secrets.randbelow(1_000_000)`;
- compute `HMAC-SHA256(OTP_HMAC_SECRET, f"{normalized_email}:{code}")` as lowercase hexadecimal;
- compare digests with `hmac.compare_digest`.

Register the auth router and shared exception handlers in `backend/app/main.py`. Configure CORS from the validated explicit origin list.

### UI

Add `frontend/src/types/auth.ts`:

```typescript
export type RequestOtpResponse = {
  expires_at: string
  otp?: string
}

export type ErrorEnvelope = {
  code: string
  message: string
  details?: Record<string, unknown>
}
```

Add `requestOtp(email)` to `frontend/src/api/client.ts`. It sends JSON to `/auth/otp/request`, parses the standard error envelope on failure, and returns `RequestOtpResponse` on `201`.

Replace the Vite demo in `frontend/src/App.tsx` with an email form. On success, keep `{ email, expiresAt, demoOtp }` in component state and show the OTP-entry step shell. Do not write email, OTP, demo OTP, expiry, or step state to browser storage.

Manual slice check:

```sh
curl -i -X POST http://127.0.0.1:8000/auth/otp/request \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com"}'
```

Expect `201`, an RFC 3339 `expires_at`, and `otp` only when both development profile and demo flag are enabled. Disable the flag and confirm the `otp` property is absent.

## Slice 2 — verify-otp

### API

Now extend the central API error mapping with `OTP_INVALID`, `OTP_EXPIRED`, `OTP_LOCKED`, `OTP_CONSUMED`, and `OTP_SUPERSEDED`; each maps to `422` and its safe client message.

Extend `backend/app/api/schemas/auth.py`:

```python
class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")


class VerifyOtpResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
```

Add `POST /auth/otp/verify`:

- status is `200 OK`;
- no Bearer credential is required;
- map the DTO to `VerifyOtpCommand(email, otp)`;
- invoke the transactional command executor, unwrap its successful `VerifyOtpData`, and return `VerifyOtpResponse` with its `datetime`;
- do not expose JWT or OTP values in logs.

All five OTP failure outcomes use the shared envelope and the codes defined in the shared design targets.

### Domain

Now create:

- `backend/app/domain/error_codes.py` with `OTP_INVALID`, `OTP_EXPIRED`, `OTP_LOCKED`, `OTP_CONSUMED`, `OTP_SUPERSEDED`, and `AUTHENTICATION_FAILED`;
- `backend/app/domain/entities/auth_session.py` with `AuthSession`;
- `backend/app/domain/token_claims.py` with `TokenClaims`;
- `TokenService` in `backend/app/domain/ports/services.py`.

Add `VerifyOtpCommand(email: str, otp: str)` and `VerifyOtpData(access_token: str, expires_at: datetime)` to `backend/app/domain/use_cases/commands/verify_otp.py`.

Now extend `backend/app/domain/ports/command_repositories.py` with:

- `UserCommandRepository.get_by_email_for_update(email) -> User | None`;
- `OtpChallengeCommandRepository.get_current_for_user_for_update(user_id) -> OtpChallenge | None`;
- `OtpChallengeCommandRepository.get_newest_by_digest_for_update(user_id, digest) -> OtpChallenge | None`;
- `OtpChallengeCommandRepository.set_failed_attempt_count(challenge_id, count) -> None`;
- `OtpChallengeCommandRepository.mark_consumed(challenge_id, consumed_at) -> None`;
- `AuthSessionCommandRepository.add(session) -> None`.

Verification always locks in this order: user, current challenge, newest digest-matching challenge. “Current” means `consumed_at IS NULL AND invalidated_at IS NULL`, with no expiry or attempt filter. “Newest digest-matching” searches every challenge for that user, including consumed, invalidated, expired, and locked rows, ordered by `created_at DESC, id DESC`, and returns one row. This lets an old submitted code map to its real state.

Use this exact failure precedence for the newest digest-matching row:

1. `consumed_at IS NOT NULL` → failed result with `OTP_CONSUMED`;
2. `invalidated_at IS NOT NULL` → failed result with `OTP_SUPERSEDED`;
3. `failed_attempt_count >= OTP_MAX_ATTEMPTS` → failed result with `OTP_LOCKED`;
4. `expires_at <= now` → failed result with `OTP_EXPIRED`;
5. otherwise it may be consumed only if it is the current row.

If no challenge matches the submitted digest, classify the current row before counting a failure:

1. no user or no current row → failed result with `OTP_INVALID`;
2. current row already locked → failed result with `OTP_LOCKED`;
3. current row expired → failed result with `OTP_EXPIRED`;
4. usable current row → increment its count and return `OTP_LOCKED` if the new count reached the maximum, otherwise return `OTP_INVALID`; normal transaction exit commits the increment.

The complete handler control flow must match this code:

```python
async def handle(self, command: VerifyOtpCommand) -> Result[VerifyOtpData]:
    email = command.email.strip().casefold()
    now = self._clock.now()
    user = await self._users.get_by_email_for_update(email)
    if user is None:
        return Result.failure(OTP_INVALID)

    current = await self._otp_challenges.get_current_for_user_for_update(
        user.id
    )
    submitted_digest = self._otp.digest(email, command.otp)
    matching = (
        await self._otp_challenges.get_newest_by_digest_for_update(
            user.id, submitted_digest
        )
    )

    if matching is not None:
        if matching.consumed_at is not None:
            return Result.failure(OTP_CONSUMED)
        if matching.invalidated_at is not None:
            return Result.failure(OTP_SUPERSEDED)
        if matching.failed_attempt_count >= self._otp_max_attempts:
            return Result.failure(OTP_LOCKED)
        if matching.expires_at <= now:
            return Result.failure(OTP_EXPIRED)
        if current is None or matching.id != current.id:
            return Result.failure(OTP_SUPERSEDED)

        session_jti = uuid4()
        token_expires_at = (
            now + timedelta(minutes=self._access_token_ttl_minutes)
        ).replace(microsecond=0)
        await self._otp_challenges.mark_consumed(matching.id, now)
        await self._auth_sessions.add(
            AuthSession(
                jti=session_jti,
                user_id=user.id,
                expires_at=token_expires_at,
                revoked_at=None,
                created_at=now,
            )
        )
        access_token = self._tokens.encode(
            user.id, session_jti, token_expires_at
        )
        return Result.success(
            VerifyOtpData(
                access_token=access_token,
                expires_at=token_expires_at,
            )
        )

    if current is None:
        return Result.failure(OTP_INVALID)
    if current.failed_attempt_count >= self._otp_max_attempts:
        return Result.failure(OTP_LOCKED)
    if current.expires_at <= now:
        return Result.failure(OTP_EXPIRED)

    new_count = current.failed_attempt_count + 1
    await self._otp_challenges.set_failed_attempt_count(
        current.id, new_count
    )
    if new_count >= self._otp_max_attempts:
        return Result.failure(OTP_LOCKED)
    return Result.failure(OTP_INVALID)
```

The constructor receives `UserCommandRepository`, `OtpChallengeCommandRepository`, `AuthSessionCommandRepository`, `OtpService`, `TokenService`, `ClockService`, `otp_max_attempts`, and `access_token_ttl_minutes`. The handler imports only domain entities, result/error definitions, and ports. Truncating the token expiry to whole seconds before both session persistence and JWT encoding keeps the database value equal to the integer JWT `exp`.

### DB

Implement challenge lookups with SQLAlchemy `select(OtpChallengeModel).with_for_update()`:

- lock the user by normalized email first;
- query current by `user_id` and the two null status columns only;
- query matching by `user_id` and exact digest across all statuses, ordered by `created_at DESC, id DESC`;
- map rows to domain entities;
- use explicit `UPDATE` statements for attempt count and consumption.

The user row lock serializes request and verify operations for one identity. The challenge row locks protect against accidental callers that bypass that convention. Do not combine current-state filters with expiry or attempt filters because doing so loses the distinction between expired, locked, and invalid.

Extend `backend/app/db/repositories/auth_repository.py` with `AuthSessionRepository` and add the `AuthSession` mapper. Keep the two repository classes separate because they implement different domain ports; only their adapter module is shared. No migration change is required because `auth_sessions` was created in Slice 1.

Implement `PyJwtTokenService` in `backend/app/auth/jwt_service.py`:

- encode HS256 with string `sub`, string `jti`, and integer `exp` from `int(expires_at.timestamp())`;
- decode with `algorithms=["HS256"]` and options requiring `sub`, `jti`, and `exp`;
- require `sub` and `jti` to be strings, reject booleans/non-integers for `exp`, convert UUIDs and UTC expiry inside the guarded block;
- catch `jwt.PyJWTError`, `KeyError`, `TypeError`, `ValueError`, and `OverflowError`;
- translate every decode or claim-conversion failure to `Result.failure(AUTHENTICATION_FAILED, reason=error)`;
- return `Result.success(TokenClaims(...))` for valid claims and never leak PyJWT exceptions.

Implement the verify-OTP transactional executor in `backend/app/dependencies.py`; compose `PyJwtTokenService`, all three command repositories, and `VerifyOtpHandler` inside one session transaction.

### UI

Extend `frontend/src/types/auth.ts`:

```typescript
export type VerifyOtpResponse = {
  access_token: string
  token_type: 'bearer'
  expires_at: string
}
```

Add `verifyOtp(email, otp)` to `frontend/src/api/client.ts`. On `200`, store only the access token:

```typescript
sessionStorage.setItem('access_token', result.access_token)
```

Complete the in-memory OTP step in `App.tsx` with a six-digit input, optional demo-code display, expiry display, submit button, and safe error text. On success, clear OTP-step state and show **Authorized** provisionally; Slice 3 adds server validation. Do not persist the OTP code or OTP-step state.

Manually exercise every state:

- wrong usable code returns `OTP_INVALID` and increments the persisted count;
- the attempt that reaches the maximum returns `OTP_LOCKED`, and later attempts remain locked;
- advancing past expiry returns `OTP_EXPIRED`;
- verifying a code once succeeds and submitting it again returns `OTP_CONSUMED`;
- request code A, request code B, then submit A to receive `OTP_SUPERSEDED`;
- code B still verifies successfully;
- successful verification returns a Bearer token and a datetime expiry.

Inspect the database after wrong attempts to prove the count committed despite the `422` response.

## Slice 3 — healthcheck

### API

Now extend the central API error mapping with `AUTHENTICATION_FAILED` → `401` and its safe client message.

Create `ContextVarCurrentUserProvider` in `backend/app/api/current_user_provider.py`. It structurally implements the domain `CurrentUserProvider.get() -> CurrentUser` port and adds adapter-only `bind(current_user)` and `reset(token)` operations. `get()` raises `RuntimeError` when no user is bound.

Create one provider instance in application composition and reuse that instance for request binding and handler injection. The stored value is task-local request context, not a process-global mutable user.

Add Bearer extraction and request binding to `backend/app/api/dependencies.py`:

```python
bearer_scheme = HTTPBearer(auto_error=False)


async def bind_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    executor: Annotated[
        GetCurrentUserExecutor, Depends(get_current_user_executor)
    ],
    provider: Annotated[
        ContextVarCurrentUserProvider,
        Depends(get_current_user_provider),
    ],
) -> AsyncIterator[None]:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        unwrap_result(Result.failure(AUTHENTICATION_FAILED))
    result = await executor(
        GetCurrentUserQuery(token=credentials.credentials)
    )
    current_user = unwrap_result(result)
    token = provider.bind(current_user)
    try:
        yield
    finally:
        provider.reset(token)
```

The exact context token returned by `bind()` must be reset in `finally`, including when the route or handler fails. Do not expose adapter mutation methods through the domain port.

`unwrap_result` is an API helper backed by the central error mapping. It returns successful data and raises only an API-layer mapping exception for a failed result; no domain exception is involved. Use `HTTPBearer(auto_error=False)`, not `OAuth2PasswordBearer`: verification accepts a JSON OTP payload and is not an OAuth2 password-form token endpoint. Manual handling guarantees missing and malformed credentials use `ErrorEnvelope`. `HTTPBearer` still registers the Bearer security scheme in OpenAPI and enables Swagger's **Authorize** button.

Add `GET /health/authenticated` in `backend/app/api/routers/health.py`:

```python
@router.get(
    "/authenticated",
    dependencies=[Depends(bind_current_user)],
)
async def health_authenticated() -> dict[str, str]:
    return {"status": "ok"}
```

Register the health router in `backend/app/main.py`. The endpoint returns `200 {"status":"ok"}` only after the complete current-user query succeeds and its result is bound for the request.

### Domain

Add frozen `CurrentUser(id, email, session_jti)` to `backend/app/domain/current_user.py`.

Add this port to `backend/app/domain/ports/current_user_provider.py`:

```python
class CurrentUserProvider(Protocol):
    def get(self) -> CurrentUser: ...
```

`CurrentUser` is the value; `CurrentUserProvider` is the behavior. Domain code never sets the provider and never imports `ContextVar` or the API implementation. Only handlers that require an authenticated HTTP principal receive this port.

Define query repository ports:

- `AuthSessionQueryRepository.get_by_jti(jti) -> AuthSession | None`;
- `UserQueryRepository.get_by_id(user_id) -> User | None`.

Add `GetCurrentUserQuery(token: str)` and `GetCurrentUserHandler` in `backend/app/domain/use_cases/queries/get_current_user.py`. The handler depends only on `TokenService`, `ClockService`, `AuthSessionQueryRepository`, and `UserQueryRepository`:

```python
async def handle(self, query: GetCurrentUserQuery) -> Result[CurrentUser]:
    claims_result = self._tokens.decode(query.token)
    if not claims_result.is_success:
        return Result.failure(
            AUTHENTICATION_FAILED,
            reason=claims_result.reason,
        )
    claims = claims_result.data
    assert claims is not None

    now = self._clock.now()
    session = await self._sessions.get_by_jti(claims.session_jti)
    if session is None:
        return Result.failure(AUTHENTICATION_FAILED)
    if session.user_id != claims.user_id:
        return Result.failure(AUTHENTICATION_FAILED)
    if session.revoked_at is not None or session.expires_at <= now:
        return Result.failure(AUTHENTICATION_FAILED)
    if session.expires_at != claims.expires_at:
        return Result.failure(AUTHENTICATION_FAILED)

    user = await self._users.get_by_id(claims.user_id)
    if user is None:
        return Result.failure(AUTHENTICATION_FAILED)
    return Result.success(
        CurrentUser(
            id=user.id,
            email=user.email,
            session_jti=session.jti,
        )
    )
```

This query decodes once, validates the active database session, and loads a fresh user row on every protected request. It creates `CurrentUser` but does not bind or read `CurrentUserProvider`; binding belongs to the incoming API adapter.

### DB

Extend `AuthSessionRepository` in `backend/app/db/repositories/auth_repository.py` with the session query operation, and extend `UserRepository` in `user_repository.py` with the user query operation:

- session lookup selects by primary-key `jti` without hiding revoked or expired rows; the domain query performs the active-state decision;
- user lookup selects the fresh user by primary key;
- both return domain entities and never expose ORM models to the handler.

The current-user query executor uses one short-lived `AsyncSession`, wires the query repositories and `GetCurrentUserHandler`, and closes the session without committing. Any implicit read transaction is rolled back on close. Composition exposes the single `ContextVarCurrentUserProvider` instance to the API binding dependency.

Keep the server-side session check even though PyJWT validates `exp`: logout and administrative revocation are database state, and the JWT alone cannot represent them.

### UI

Centralize authenticated fetch behavior in `frontend/src/api/client.ts`:

- read `access_token` from `sessionStorage` immediately before each authenticated request;
- attach `Authorization: Bearer ${token}`;
- on **any** `401`, remove `access_token` before returning an `ApiError`;
- do not clear the token for non-`401` errors.

Add `checkAuthenticated()` for `GET /health/authenticated`.

On `App` mount:

1. if no token exists, show the email form;
2. if a token exists, show a neutral loading state and call `checkAuthenticated()`;
3. on `200`, show **Authorized**;
4. on `401`, rely on the client to clear the token and show the email form;
5. on a network or `5xx` error, show a retryable error without silently deleting the token.

Manual checks:

```sh
curl -i http://127.0.0.1:8000/health/authenticated
curl -i http://127.0.0.1:8000/health/authenticated \
  -H 'Authorization: Bearer malformed'
curl -i http://127.0.0.1:8000/health/authenticated \
  -H "Authorization: Bearer $TOKEN"
```

The first two responses are `401` with `code`, `message`, and `details`; the valid active token returns `200`. Reload the browser with a valid token and confirm **Authorized** returns after the check.

## Slice 4 — logout

### API

Add `POST /auth/logout` to `backend/app/api/routers/auth.py`:

```python
@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(bind_current_user)],
)
async def logout(
    executor: Annotated[LogoutExecutor, Depends(get_logout_executor)],
) -> Response:
    result = await executor(LogoutCommand())
    unwrap_result(result)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

The authentication dependency validates the token once and binds `CurrentUser` for the request. The route does not receive the value, raw credentials, or `session_jti`; the domain handler obtains it through `CurrentUserProvider`. A missing, malformed, expired, or already-revoked session returns the same standard `401` envelope as healthcheck.

### Domain

Add fieldless `LogoutCommand` and `LogoutHandler` in `backend/app/domain/use_cases/commands/logout.py`.

Extend `AuthSessionCommandRepository` with `revoke(jti: UUID, revoked_at: datetime) -> bool`. The exact handler is:

```python
async def handle(self, command: LogoutCommand) -> Result[None]:
    current_user = self._current_user.get()
    changed = await self._auth_sessions.revoke(
        current_user.session_jti, self._clock.now()
    )
    if not changed:
        return Result.failure(AUTHENTICATION_FAILED)
    return Result.success()
```

The handler depends on `CurrentUserProvider`, `AuthSessionCommandRepository`, and `ClockService`. The provider is a constructor dependency, not a global import. The handler revokes one `jti`; it never updates every session belonging to the user.

### DB

Implement revocation as one guarded update:

```sql
UPDATE auth_sessions
SET revoked_at = :revoked_at
WHERE jti = :jti
  AND revoked_at IS NULL
  AND expires_at > :revoked_at;
```

Return `rowcount == 1`. Do not filter or update by `user_id`. No schema migration is required.

Implement the logout transactional executor in `backend/app/dependencies.py` using the shared `ContextVarCurrentUserProvider` instance, `AuthSessionRepository`, and the shared clock. The API authentication dependency and logout executor may use separate short-lived database sessions; the former binds `CurrentUser`, while the guarded update makes the command safe if revocation occurs between those operations.

### UI

Add `logout()` to `frontend/src/api/client.ts`. It sends an authenticated `POST /auth/logout` with no body.

When the user clicks **Logout**:

- on `204`, remove `access_token`, clear all authentication UI state, and show the email form;
- on `401`, the shared client removes the token, then the UI shows the email form;
- on a network or `5xx` error, keep the token and show a retryable error because server-side revocation is unknown.

Create two independent browser sessions or obtain two tokens for the same email. Log out with token A, then prove token A receives `401` while token B still receives `200`.

## Final verification

Prerequisites: PostgreSQL is healthy, the reviewed migration is applied, the backend runs on port 8000, and the frontend runs on port 5173.

- [ ] Request OTP normalizes email and concurrent requests leave exactly one current challenge.
- [ ] Request OTP invalidates every prior current challenge, including expired or locked rows.
- [ ] Demo `otp` appears only with `APP_ENV=development` and `ENABLE_DEMO_OTP=true`; otherwise the property is omitted, never `null`.
- [ ] Wrong current OTP increments its count and returns a failed `Result`; normal transaction exit commits the count for both `OTP_INVALID` and threshold `OTP_LOCKED`.
- [ ] Invalid, expired, locked, consumed, and superseded OTPs each return the correct `422` envelope.
- [ ] A successful OTP is consumed, creates an active session, and returns a JWT with valid `sub`, `jti`, and integer `exp`.
- [ ] Malformed JWT claims and claim conversions return `401 AUTHENTICATION_FAILED` without leaking adapter exceptions.
- [ ] `GET /health/authenticated` returns `200` for an active session and the standard `401` envelope for missing, malformed, expired, or revoked credentials.
- [ ] The API binds `CurrentUser` only for an authenticated request, protected handlers read it through `CurrentUserProvider`, and `finally` reset prevents state leaking into later requests.
- [ ] Reload during OTP entry returns to the email form; reload with a valid stored token restores **Authorized** after the authenticated health request.
- [ ] Any frontend `401` clears the token; non-`401` transient failures do not.
- [ ] Logout obtains `CurrentUser.session_jti` through the provider and revokes only that session; another session for the same user remains active.
- [ ] Unexpected command exceptions escape the handler and roll back the transaction rather than becoming failed `Result` values.
- [ ] Swagger shows Bearer authorization and can exercise authenticated health and logout after pasting a token.
- [ ] No OTP, JWT, HMAC secret, signing secret, or request-OTP response body appears in logs.

Run static quality checks only; automated tests remain outside this phase:

```sh
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app

cd ../frontend
yarn lint
yarn typecheck
```
