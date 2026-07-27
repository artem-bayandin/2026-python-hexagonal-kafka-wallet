# Phase 2 — Authentication

Implement email OTP authentication end to end in four vertical slices, in this exact order:

1. `request-otp`
2. `verify-otp`
3. `healthcheck`
4. `logout`

Within every slice, work in the strict order **API → Domain → DB → UI**. Do not run or demonstrate a slice until all four sections in that slice are complete.

Canonical behavior is defined by [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md), [API_CONTRACT.md](../API_CONTRACT.md), [CONFIGURATION.md](../CONFIGURATION.md), and [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md). Those documents and this guide are aligned on the phase-specific scope below.

## Scope

This phase includes OTP request and verification, Bearer access tokens, server-side authentication sessions, authenticated health, logout, and the minimal React login/authenticated state.

This phase deliberately excludes:

- wallet `accounts`; add them in roadmap **Step 4 — Model accounts, balances, and transactions**;
- `users.is_active`; add and enforce it with the later wallet authorization work in roadmap **Step 9 — Build and compose the HTTP API**;
- automated tests; complete the deferred authentication unit tests from roadmap Steps 3, 6, and 7 together with the integration coverage in **Step 11 — Complete version-1 integration coverage**;
- HTTP idempotency; it is deferred entirely to the roadmap's final optional hardening phase.

Use manual verification and the static quality checks in this guide. Do not add test files during this phase.

## Done when

A browser can request a development demo OTP, verify it, show **Authorized**, survive a reload by validating the token against `GET /health/authenticated`, and log out only the current session. Reloading during OTP entry returns to the email form because the OTP step exists only in React memory. Missing, malformed, expired, or revoked credentials always produce the standard `401` error envelope. Backend ruff/mypy and frontend lint/typecheck pass.

## Architecture rules

- `backend/app/domain/` imports only Python standard-library modules and other domain models or `Protocol` ports.
- Domain handlers never import FastAPI, Pydantic, SQLAlchemy, PyJWT, `app.auth`, or `app.db`.
- `backend/app/domain/ports/services.py` owns `ClockService`, `OtpService`, and `TokenService`.
- `backend/app/domain/ports/unit_of_work.py` owns `UnitOfWork`.
- SQLAlchemy repositories and `SqlAlchemyUnitOfWork` live under `backend/app/db/` and structurally implement domain ports.
- HMAC/`secrets` and PyJWT implementations live under `backend/app/auth/` and structurally implement domain ports.
- `backend/app/dependencies.py` is the composition root. Routers and API dependencies obtain already-composed handlers from it.
- API routers translate HTTP DTOs to commands and results to response DTOs. Domain-to-HTTP exception mapping lives only in `backend/app/api/exception_handlers.py`.
- Every command in this phase owns an explicit transaction through `UnitOfWork`. In particular, a wrong OTP attempt must be committed before `OtpInvalidError` or `OtpLockedError` is raised.

## Shared design and bootstrap

Before Slice 1, update configuration and create only package directories that do not yet exist. The remaining subsections in this section define shared targets; do not implement their layer-owned files here. Slice 1 explicitly activates each target in API → Domain → DB order. Alembic initialization and all database work wait for Slice 1 DB.

### Target layout

Create these packages as they become needed:

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
    │   ├── dependencies.py
    │   ├── exception_handlers.py
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
    │   ├── unit_of_work.py
    │   └── repositories/
    │       ├── auth_repository.py
    │       └── user_repository.py
    └── domain/
        ├── current_user.py
        ├── exceptions.py
        ├── entities/
        │   ├── auth_session.py
        │   ├── otp_challenge.py
        │   └── user.py
        ├── ports/
        │   ├── command_repositories.py
        │   ├── query_repositories.py
        │   ├── services.py
        │   └── unit_of_work.py
        └── use_cases/
            ├── commands/
            │   ├── logout.py
            │   ├── request_otp.py
            │   └── verify_otp.py
            └── queries/
                └── get_current_user.py
```

Alembic belongs under `backend/` in this repository. Run this only when Slice 1 reaches its DB section:

```sh
cd backend
uv run alembic init alembic
```

Configure `backend/alembic/env.py` to import `Base` from `app.db.models`, set `target_metadata = Base.metadata`, use the async migration pattern, and obtain the URL from `get_settings().database_url`. Keep `backend/alembic.ini` beside `pyproject.toml`.

### Configuration

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

The demo OTP is returned only when both conditions are true:

```python
include_demo_otp = (
    settings.app_env is AppEnv.DEVELOPMENT and settings.enable_demo_otp
)
```

### Shared domain contracts

When Slice 1 reaches Domain, create these framework-free dataclasses:

- `User(id: UUID, email: str, created_at: datetime)`;
- `OtpChallenge(id: UUID, user_id: UUID, otp_digest: str, expires_at: datetime, failed_attempt_count: int, consumed_at: datetime | None, invalidated_at: datetime | None, created_at: datetime)`;
- `AuthSession(jti: UUID, user_id: UUID, expires_at: datetime, revoked_at: datetime | None, created_at: datetime)`;
- `TokenClaims(user_id: UUID, session_jti: UUID, expires_at: datetime)`;
- frozen `CurrentUser(id: UUID, email: str, session_jti: UUID)`.

At that same Domain step, create these exceptions in `backend/app/domain/exceptions.py`: `DomainError`, `OtpInvalidError`, `OtpExpiredError`, `OtpLockedError`, `OtpConsumedError`, `OtpSupersededError`, and `AuthenticationFailedError`. Each carries only a client-safe message.

Define these structural service ports in `backend/app/domain/ports/services.py` during Slice 1 Domain:

- `ClockService.now() -> datetime`; implementations must return timezone-aware UTC;
- `OtpService.generate_code() -> str`;
- `OtpService.digest(normalized_email: str, code: str) -> str`;
- `OtpService.matches(normalized_email: str, code: str, expected_digest: str) -> bool`;
- `TokenService.encode(user_id: UUID, session_jti: UUID, expires_at: datetime) -> str`;
- `TokenService.decode(token: str) -> TokenClaims`.

Define repository ports in `command_repositories.py` and `query_repositories.py` with the exact operations named by the slices. During Slice 1 Domain, define `UnitOfWork` in `unit_of_work.py` with `users`, `otp_challenges`, and `auth_sessions` command-repository properties plus async `commit()` and `rollback()` methods. Protocol declarations may use method bodies that raise `NotImplementedError`; do not place adapter behavior in the domain.

### Shared transaction rule

Implement this rule only when Slice 1 reaches DB: `backend/app/db/unit_of_work.py` wraps one `AsyncSession`. All repositories held by one unit of work share that session. `commit()` calls `session.commit()` and `rollback()` calls `session.rollback()`.

The request-scoped provider in `backend/app/dependencies.py` must not auto-commit:

```python
async def get_uow(request: Request) -> AsyncIterator[SqlAlchemyUnitOfWork]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        try:
            yield uow
        finally:
            if session.in_transaction():
                await session.rollback()
```

Command handlers call `commit()` at the exact points specified below. This makes the invalid-attempt rule possible: update the attempt count, commit that update, then raise the typed error. A generic “rollback on every exception” wrapper would erase the attempt and must not be used around this handler.

### Shared database model

The first migration, created during Slice 1 DB, creates only `users`, `otp_challenges`, and `auth_sessions`.

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

Add indexes on `otp_challenges(user_id, created_at DESC)` and `auth_sessions(user_id)`. Add this partial unique index:

```sql
CREATE UNIQUE INDEX uq_otp_challenges_one_current_per_user
ON otp_challenges (user_id)
WHERE consumed_at IS NULL AND invalidated_at IS NULL;
```

“Current” deliberately ignores expiry and failed-attempt count. An expired or locked challenge remains current until it is consumed or invalidated, so request and verification can classify it correctly. The partial index guarantees at most one current row per user.

### Shared API errors

Create `backend/app/api/schemas/errors.py` when Slice 1 reaches API:

```python
from typing import Any

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
```

`backend/app/api/exception_handlers.py` is the only exception-to-HTTP mapping:

| Exception | Status | Code |
| --- | --- | --- |
| request validation | `422` | `VALIDATION_ERROR` |
| `OtpInvalidError` | `422` | `OTP_INVALID` |
| `OtpExpiredError` | `422` | `OTP_EXPIRED` |
| `OtpLockedError` | `422` | `OTP_LOCKED` |
| `OtpConsumedError` | `422` | `OTP_CONSUMED` |
| `OtpSupersededError` | `422` | `OTP_SUPERSEDED` |
| `AuthenticationFailedError` | `401` | `AUTHENTICATION_FAILED` |

Every handled response, including every `401`, is an `ErrorEnvelope`. Never allow FastAPI's security helper to emit its default non-envelope authentication response.

## Slice 1 — request-otp

### API

Implement the shared API error schema and exception-handler mapping defined above, then add the request-OTP DTOs and route.

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
- return the handler's timezone-aware `datetime` directly;
- declare `response_model=RequestOtpResponse` and `response_model_exclude_none=True`.

The last setting is mandatory: when demo output is disabled, `otp` is omitted rather than serialized as `null`. Never log request-OTP response bodies.

### Domain

Implement the shared domain entities, exceptions, service ports, command-repository ports, and `UnitOfWork` port defined above before adding this slice's command handler.

Add `RequestOtpCommand(email: str)` and `RequestOtpResult(expires_at: datetime, demo_otp: str | None)` to `backend/app/domain/use_cases/commands/request_otp.py`.

Repository contracts used by this handler:

- `UserCommandRepository.ensure_by_email(email, user_id, created_at) -> None`;
- `UserCommandRepository.get_by_email_for_update(email) -> User`;
- `OtpChallengeCommandRepository.invalidate_current_for_user(user_id, invalidated_at) -> int`;
- `OtpChallengeCommandRepository.add(challenge) -> None`.

Normalize email once with `email.strip().casefold()`. The handler algorithm is exact:

```python
async def handle(self, command: RequestOtpCommand) -> RequestOtpResult:
    email = command.email.strip().casefold()
    now = self._clock.now()
    proposed_user_id = uuid4()

    await self._uow.users.ensure_by_email(email, proposed_user_id, now)
    user = await self._uow.users.get_by_email_for_update(email)

    await self._uow.otp_challenges.invalidate_current_for_user(user.id, now)

    code = self._otp.generate_code()
    expires_at = now + timedelta(seconds=self._otp_ttl_seconds)
    await self._uow.otp_challenges.add(
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
    await self._uow.commit()

    return RequestOtpResult(
        expires_at=expires_at,
        demo_otp=code if self._include_demo_otp else None,
    )
```

Imports for this module come only from `dataclasses`, `datetime`, `uuid`, domain entities, and domain ports. The constructor receives `UnitOfWork`, `OtpService`, `ClockService`, `otp_ttl_seconds`, and `include_demo_otp`.

### DB

Implement the shared database model, transaction provider, SQLAlchemy unit of work, ORM mappings, and migration defined above before composing this slice.

Implement `backend/app/db/repositories/user_repository.py`:

1. `ensure_by_email` executes `INSERT INTO users (id, email, created_at) VALUES (:id, :email, :created_at) ON CONFLICT (email) DO NOTHING`.
2. `get_by_email_for_update` selects the complete `UserModel` where `email = :email` and applies `FOR UPDATE`.
3. The insert and select run in the same transaction. If another request is creating the same email, PostgreSQL waits for that insert to resolve; the subsequent row lock serializes challenge changes for that user.

Implement `OtpChallengeRepository` in `backend/app/db/repositories/auth_repository.py`:

- `invalidate_current_for_user` updates **all** rows for the user where both `consumed_at IS NULL` and `invalidated_at IS NULL`; do not filter by expiry or attempt count;
- execute the invalidation as an explicit SQL `UPDATE` before adding the replacement row, so the partial unique predicate is cleared first;
- `add` maps the domain entity to an ORM model and adds it to the session.

This lock order is mandatory for every OTP request: atomic user insert, lock user, execute the current-challenge invalidation, insert the new challenge, commit. The user lock plus partial unique index makes concurrent requests deterministic and prevents two current challenges.

Add SQLAlchemy models and domain/ORM mappers in `backend/app/db/models.py` and `backend/app/db/mappers.py`. Generate, review, and apply the migration:

```sh
cd backend
uv run alembic revision --autogenerate -m "add authentication tables"
uv run alembic upgrade head
```

Confirm the generated revision contains the partial unique index with the exact predicate above. If autogenerate omits the predicate, add an `op.create_index` call named `uq_otp_challenges_one_current_per_user`, over `["user_id"]`, with `unique=True` and `postgresql_where=sa.text("consumed_at IS NULL AND invalidated_at IS NULL")`.

In `backend/app/dependencies.py`, compose `SystemClock`, `HmacOtpService`, `SqlAlchemyUnitOfWork`, and `RequestOtpHandler`. `HmacOtpService` in `backend/app/auth/otp_service.py` must:

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
- return `VerifyOtpResponse` with the handler's `datetime`;
- do not expose JWT or OTP values in logs.

All five OTP failure outcomes use the shared envelope and the codes defined in the bootstrap.

### Domain

Add `VerifyOtpCommand(email: str, otp: str)` and `VerifyOtpResult(access_token: str, expires_at: datetime)`.

Extend repository contracts:

- `UserCommandRepository.get_by_email_for_update(email) -> User | None`;
- `OtpChallengeCommandRepository.get_current_for_user_for_update(user_id) -> OtpChallenge | None`;
- `OtpChallengeCommandRepository.get_newest_by_digest_for_update(user_id, digest) -> OtpChallenge | None`;
- `OtpChallengeCommandRepository.set_failed_attempt_count(challenge_id, count) -> None`;
- `OtpChallengeCommandRepository.mark_consumed(challenge_id, consumed_at) -> None`;
- `AuthSessionCommandRepository.add(session) -> None`.

Verification always locks in this order: user, current challenge, newest digest-matching challenge. “Current” means `consumed_at IS NULL AND invalidated_at IS NULL`, with no expiry or attempt filter. “Newest digest-matching” searches every challenge for that user, including consumed, invalidated, expired, and locked rows, ordered by `created_at DESC, id DESC`, and returns one row. This lets an old submitted code map to its real state.

Use this exact failure precedence for the newest digest-matching row:

1. `consumed_at IS NOT NULL` → `OtpConsumedError`;
2. `invalidated_at IS NOT NULL` → `OtpSupersededError`;
3. `failed_attempt_count >= OTP_MAX_ATTEMPTS` → `OtpLockedError`;
4. `expires_at <= now` → `OtpExpiredError`;
5. otherwise it may be consumed only if it is the current row.

If no challenge matches the submitted digest, classify the current row before counting a failure:

1. no user or no current row → `OtpInvalidError`;
2. current row already locked → `OtpLockedError`;
3. current row expired → `OtpExpiredError`;
4. usable current row → increment its count and commit; raise `OtpLockedError` if the new count reached the maximum, otherwise raise `OtpInvalidError`.

The complete handler control flow must match this code:

```python
async def handle(self, command: VerifyOtpCommand) -> VerifyOtpResult:
    email = command.email.strip().casefold()
    now = self._clock.now()
    user = await self._uow.users.get_by_email_for_update(email)
    if user is None:
        raise OtpInvalidError("The OTP is invalid.")

    current = await self._uow.otp_challenges.get_current_for_user_for_update(
        user.id
    )
    submitted_digest = self._otp.digest(email, command.otp)
    matching = (
        await self._uow.otp_challenges.get_newest_by_digest_for_update(
            user.id, submitted_digest
        )
    )

    if matching is not None:
        if matching.consumed_at is not None:
            raise OtpConsumedError("The OTP was already used.")
        if matching.invalidated_at is not None:
            raise OtpSupersededError("The OTP was replaced by a newer code.")
        if matching.failed_attempt_count >= self._otp_max_attempts:
            raise OtpLockedError("The OTP is locked.")
        if matching.expires_at <= now:
            raise OtpExpiredError("The OTP has expired.")
        if current is None or matching.id != current.id:
            raise OtpSupersededError("The OTP was replaced by a newer code.")

        session_jti = uuid4()
        token_expires_at = (
            now + timedelta(minutes=self._access_token_ttl_minutes)
        ).replace(microsecond=0)
        await self._uow.otp_challenges.mark_consumed(matching.id, now)
        await self._uow.auth_sessions.add(
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
        await self._uow.commit()
        return VerifyOtpResult(
            access_token=access_token,
            expires_at=token_expires_at,
        )

    if current is None:
        raise OtpInvalidError("The OTP is invalid.")
    if current.failed_attempt_count >= self._otp_max_attempts:
        raise OtpLockedError("The OTP is locked.")
    if current.expires_at <= now:
        raise OtpExpiredError("The OTP has expired.")

    new_count = current.failed_attempt_count + 1
    await self._uow.otp_challenges.set_failed_attempt_count(
        current.id, new_count
    )
    await self._uow.commit()
    if new_count >= self._otp_max_attempts:
        raise OtpLockedError("The OTP is locked.")
    raise OtpInvalidError("The OTP is invalid.")
```

The constructor receives `UnitOfWork`, `OtpService`, `TokenService`, `ClockService`, `otp_max_attempts`, and `access_token_ttl_minutes`. The handler imports only domain entities and ports. Truncating the token expiry to whole seconds before both session persistence and JWT encoding keeps the database value equal to the integer JWT `exp`.

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
- translate every decode or claim-conversion failure to `AuthenticationFailedError("Invalid or expired token.")`;
- return `TokenClaims` and never leak PyJWT exceptions.

Wire `PyJwtTokenService` and `VerifyOtpHandler` in `backend/app/dependencies.py`.

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

Add Bearer extraction to `backend/app/api/dependencies.py`:

```python
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    handler: Annotated[
        GetCurrentUserHandler, Depends(get_current_user_handler)
    ],
) -> CurrentUser:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise AuthenticationFailedError("Authentication failed.")
    return await handler.handle(
        GetCurrentUserQuery(token=credentials.credentials)
    )
```

Use `HTTPBearer(auto_error=False)`, not `OAuth2PasswordBearer`: verification accepts a JSON OTP payload and is not an OAuth2 password-form token endpoint. Manual handling guarantees missing and malformed credentials use `ErrorEnvelope`. `HTTPBearer` still registers the Bearer security scheme in OpenAPI and enables Swagger's **Authorize** button.

Add `GET /health/authenticated` in `backend/app/api/routers/health.py`:

```python
@router.get("/authenticated")
async def health_authenticated(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    return {"status": "ok"}
```

Register the health router in `backend/app/main.py`. The endpoint returns `200 {"status":"ok"}` only after the complete current-user query succeeds.

### Domain

Add frozen `CurrentUser(id, email, session_jti)` to `backend/app/domain/current_user.py`.

Define query repository ports:

- `AuthSessionQueryRepository.get_by_jti(jti) -> AuthSession | None`;
- `UserQueryRepository.get_by_id(user_id) -> User | None`.

Add `GetCurrentUserQuery(token: str)` and `GetCurrentUserHandler` in `backend/app/domain/use_cases/queries/get_current_user.py`. The handler depends only on `TokenService`, `ClockService`, `AuthSessionQueryRepository`, and `UserQueryRepository`:

```python
async def handle(self, query: GetCurrentUserQuery) -> CurrentUser:
    claims = self._tokens.decode(query.token)
    now = self._clock.now()
    session = await self._sessions.get_by_jti(claims.session_jti)
    if session is None:
        raise AuthenticationFailedError("Authentication failed.")
    if session.user_id != claims.user_id:
        raise AuthenticationFailedError("Authentication failed.")
    if session.revoked_at is not None or session.expires_at <= now:
        raise AuthenticationFailedError("Authentication failed.")
    if session.expires_at != claims.expires_at:
        raise AuthenticationFailedError("Authentication failed.")

    user = await self._users.get_by_id(claims.user_id)
    if user is None:
        raise AuthenticationFailedError("Authentication failed.")
    return CurrentUser(
        id=user.id,
        email=user.email,
        session_jti=session.jti,
    )
```

This query decodes once, validates the active database session, and loads a fresh user row on every protected request. There is no `is_active` field in this phase.

### DB

Extend `AuthSessionRepository` in `backend/app/db/repositories/auth_repository.py` with the session query operation, and extend `UserRepository` in `user_repository.py` with the user query operation:

- session lookup selects by primary-key `jti` without hiding revoked or expired rows; the domain query performs the active-state decision;
- user lookup selects the fresh user by primary key;
- both return domain entities and never expose ORM models to the handler.

Read-only dependencies use one request-scoped `AsyncSession`, roll back any implicit read transaction on close, and never commit. Wire the query repositories and `GetCurrentUserHandler` in `backend/app/dependencies.py`.

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
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    handler: Annotated[LogoutHandler, Depends(get_logout_handler)],
) -> Response:
    await handler.handle(
        LogoutCommand(session_jti=current_user.session_jti)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

The route reuses `CurrentUser.session_jti`; it does not receive raw credentials and does not decode the JWT a second time. A missing, malformed, expired, or already-revoked session returns the same standard `401` envelope as healthcheck.

### Domain

Add `LogoutCommand(session_jti: UUID)` and `LogoutHandler` in `backend/app/domain/use_cases/commands/logout.py`.

Extend `AuthSessionCommandRepository` with `revoke(jti: UUID, revoked_at: datetime) -> bool`. The exact handler is:

```python
async def handle(self, command: LogoutCommand) -> None:
    changed = await self._uow.auth_sessions.revoke(
        command.session_jti, self._clock.now()
    )
    if not changed:
        await self._uow.rollback()
        raise AuthenticationFailedError("Authentication failed.")
    await self._uow.commit()
```

The handler depends only on `UnitOfWork` and `ClockService`. It revokes one `jti`; it never updates every session belonging to the user.

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

Wire `LogoutHandler` in `backend/app/dependencies.py` using a command unit of work and the shared clock. The API current-user dependency and logout handler may use separate short-lived sessions; the former authenticates and supplies `session_jti`, while the guarded update makes the command safe if revocation occurs between those operations.

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
- [ ] Wrong current OTP increments and commits its count before `OTP_INVALID`; the threshold attempt commits and returns `OTP_LOCKED`.
- [ ] Invalid, expired, locked, consumed, and superseded OTPs each return the correct `422` envelope.
- [ ] A successful OTP is consumed, creates an active session, and returns a JWT with valid `sub`, `jti`, and integer `exp`.
- [ ] Malformed JWT claims and claim conversions return `401 AUTHENTICATION_FAILED` without leaking adapter exceptions.
- [ ] `GET /health/authenticated` returns `200` for an active session and the standard `401` envelope for missing, malformed, expired, or revoked credentials.
- [ ] Reload during OTP entry returns to the email form; reload with a valid stored token restores **Authorized** after the authenticated health request.
- [ ] Any frontend `401` clears the token; non-`401` transient failures do not.
- [ ] Logout revokes only the session identified by `CurrentUser.session_jti`; another session for the same user remains active.
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
