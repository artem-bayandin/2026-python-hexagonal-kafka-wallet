# Phase 2 — Authentication

Complete Slice 0 configuration first, then implement email OTP authentication end to end in four vertical feature slices, in this exact order:

1. `request-otp`
2. `verify-otp`
3. `healthcheck`
4. `logout`

Within each feature slice, work in the strict order **Domain → DB → API → UI**. Do not run or demonstrate a feature slice until all four sections in that slice are complete.

## Current implementation status

- **Slice 0 — configuration:** complete.
- **Slice 1 — Domain:** complete.
- **Slice 1 — DB persistence:** complete through the generated and reviewed Alembic revision, including the users, OTP-challenge, and authentication-session schema.
- **Next:** complete Slice 1 application composition from `backend/app/dependencies.py`, then finish its API and UI sections. Existing API scaffold files are not a completed or runnable API until that work is done.

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
- `app.api`, `app.auth`, `app.db`, and `app.domain` are regular packages with an `__init__.py` public façade. A different layer imports only symbols re-exported by that façade (for example, `from app.domain import Result`), never its nested implementation modules. Same-layer imports may remain concrete to avoid circular dependencies.
- Every command and query handler returns the immutable generic `Result[T]` from `app.domain`.
- `CurrentUser` is an immutable domain value; `CurrentUserProvider` is a domain port implemented by the API with request-scoped state.
- Domain ports are split by responsibility and main entity: `ports/services/<service>.py` for services and `ports/repositories/<entity>_repository.py` for repositories.
- SQLAlchemy repositories live under `backend/app/db/repositories/<entity>_repository.py` and structurally implement their matching domain ports. Concrete classes use the `*Impl` suffix (for example `UserRepositoryImpl`) so they do not collide with domain Protocol names when re-exported from `app.db`.
- Domain use cases live under `backend/app/domain/use_cases/<entity>/`, not a shared `commands/` or `queries/` directory.
- HMAC/`secrets`, clock, and PyJWT implementations live under `backend/app/auth/` and structurally implement domain ports.
- `backend/app/dependencies.py` is the composition root. It opens SQLAlchemy transaction contexts, composes handlers with repositories sharing one session, invokes the handler, and returns its `Result`.
- API routers translate HTTP DTOs to commands and successful result data to response DTOs. Result-error-code-to-HTTP mapping lives only in `backend/app/api/exception_handlers.py`.
- Every command executes inside `AsyncSession.begin()`. A returned `Result`, whether successful or failed, exits normally and commits; an unexpected exception escapes and rolls back.

## Shared implementation notes

This section is reference material, not an implementation stage. It contains no create/update step. Complete file contents and schema definitions appear in Slice 1–4 at the point they are created or updated, preserving the Domain → DB → API → UI order.

### Target layout

Use this final target layout as a reference only:

```text
backend/
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
└── app/
    ├── __init__.py
    ├── config.py
    ├── dependencies.py
    ├── main.py
    ├── api/
    │   ├── __init__.py
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
    │   ├── __init__.py
    │   ├── jwt_service.py
    │   ├── otp_service.py
    │   └── system_clock.py
    ├── db/
    │   ├── __init__.py
    │   ├── mappers/
    │   │   ├── __init__.py
    │   │   ├── auth_session.py
    │   │   ├── otp_challenge.py
    │   │   └── user.py
    │   ├── models/
    │   │   ├── __init__.py
    │   │   ├── auth_session.py
    │   │   ├── base.py
    │   │   ├── otp_challenge.py
    │   │   └── user.py
    │   ├── session.py
    │   └── repositories/
    │       ├── auth_session_repository.py
    │       ├── otp_challenge_repository.py
    │       └── user_repository.py
    └── domain/
        ├── __init__.py
        ├── current_user.py
        ├── error_codes.py
        ├── result.py
        ├── token_claims.py
        ├── entities/
        │   ├── __init__.py
        │   ├── auth_session.py
        │   ├── otp_challenge.py
        │   └── user.py
        ├── ports/
        │   ├── __init__.py
        │   ├── current_user_provider.py
        │   ├── repositories/
        │   │   ├── auth_session_repository.py
        │   │   ├── otp_challenge_repository.py
        │   │   └── user_repository.py
        │   └── services/
        │       ├── clock_service.py
        │       ├── otp_service.py
        │       └── token_service.py
        └── use_cases/
            ├── __init__.py
            ├── auth_session/
            │   └── logout_cmd.py
            ├── otp/
            │   ├── request_otp_cmd.py
            │   └── verify_otp_cmd.py
            └── user/
                └── get_current_user_query.py
```

### Shared transaction target

The transaction target is one `AsyncSession.begin()` context per command. Every repository used by that command shares the session. Domain handlers never call `commit()` or `rollback()`: a returned `Result`, including a failed result, exits normally and commits intentional changes, while an unexpected exception escapes and triggers automatic rollback.

## Slice 0 — configuration

Complete this preparation before Slice 1. It changes only the existing configuration files named below; do not create any directories or other files from the target layout yet.

Implemented configuration in `backend/.env.example` and the gitignored `backend/.env`:

```dotenv
JWT_ACCESS_TOKEN_TTL_MINUTES=60
OTP_TTL_SECONDS=300
OTP_MAX_ATTEMPTS=5
ENABLE_DEMO_OTP=false
```

`backend/app/config.py` uses these contracts:

- `Settings.app_env` is a plain string. Development composition checks `settings.app_env == "development"`.
- `jwt_access_token_ttl_minutes`, `otp_ttl_seconds`, and `otp_max_attempts` are integers declared with `Field(gt=0)`.
- `jwt_secret` and `otp_hmac_secret` are `SecretStr`.
- `enable_demo_otp` defaults to `False`; the Slice 1 composition gate controls whether the OTP is exposed.
- `cors_allowed_origins` remains a comma-separated string with the development default `http://127.0.0.1:5173`.
- Keep `Settings` declarative: do not add field or model validators for secret length/equality, profile combinations, or CORS origins.
- Do not log settings or secret values.

## Slice 1 — request-otp

### Domain

Create `backend/app/domain/result.py` (return annotations may use `Self` or quoted `Result[T]`):

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    _data: T | None = None
    _error_code: str | None = None
    _reason: Exception | None = None

    def __post_init__(self) -> None:
        valid_success = self._error_code is None and self._reason is None
        valid_failure = (
            self._error_code is not None
            and bool(self._error_code)
            and self._data is None
        )
        if not (valid_success or valid_failure):
            raise ValueError("Invalid Result initialization.")

    @classmethod
    def success(cls, data: T | None = None) -> Result[T]:
        return cls(_data=data)

    @classmethod
    def failure(
        cls, error_code: str, reason: Exception | None = None
    ) -> Result[T]:
        return cls(_error_code=error_code, _reason=reason)

    @property
    def is_success(self) -> bool:
        return self._error_code is None

    @property
    def data(self) -> T | None:
        return self._data

    @property
    def error_code(self) -> str | None:
        return self._error_code

    @property
    def reason(self) -> Exception | None:
        return self._reason
```

Every command and query returns `Result[T]`. Expected OTP and authentication outcomes return `Result.failure`; unexpected infrastructure and programming failures remain exceptions so the SQLAlchemy transaction context rolls back. `reason` is internal diagnostic context and is never serialized, exposed to clients, or logged automatically.

Create `backend/app/domain/entities/user.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    created_at: datetime
```

Create `backend/app/domain/entities/otp_challenge.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OtpChallenge:
    id: UUID
    user_id: UUID
    otp_digest: str
    expires_at: datetime
    failed_attempt_count: int
    consumed_at: datetime | None
    invalidated_at: datetime | None
    created_at: datetime
```

Create `backend/app/domain/ports/services/clock_service.py`:

```python
from datetime import datetime
from typing import Protocol


class ClockService(Protocol):
    def now(self) -> datetime: ...
```

Create `backend/app/domain/ports/services/otp_service.py`:

```python
from typing import Protocol


class OtpService(Protocol):
    def generate_code(self) -> str: ...

    def digest(self, normalized_email: str, code: str) -> str: ...

    def matches(
        self, normalized_email: str, code: str, expected_digest: str
    ) -> bool: ...
```

`ClockService.now()` implementations must return timezone-aware UTC datetimes.

Create `backend/app/domain/ports/repositories/user_repository.py`:

```python
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities.user import User


class UserRepository(Protocol):
    async def ensure_by_email(
        self, email: str, user_id: UUID, created_at: datetime
    ) -> None: ...

    async def get_by_email_for_update(self, email: str) -> User: ...
```

Create `backend/app/domain/ports/repositories/otp_challenge_repository.py`:

```python
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities.otp_challenge import OtpChallenge


class OtpChallengeRepository(Protocol):
    async def invalidate_current_for_user(
        self, user_id: UUID, invalidated_at: datetime
    ) -> int: ...

    async def add(self, challenge: OtpChallenge) -> None: ...
```

Create `backend/app/domain/use_cases/otp/request_otp_cmd.py` with `RequestOtpCommand`, `RequestOtpData`, and `RequestOtpHandler`.

Normalize email once with `email.strip().casefold()`. The complete handler is:

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from app.domain.entities.otp_challenge import OtpChallenge
from app.domain.ports.repositories.otp_challenge_repository import (
    OtpChallengeRepository,
)
from app.domain.ports.repositories.user_repository import UserRepository
from app.domain.ports.services.clock_service import ClockService
from app.domain.ports.services.otp_service import OtpService
from app.domain.result import Result


@dataclass(frozen=True, slots=True)
class RequestOtpCommand:
    email: str


@dataclass(frozen=True, slots=True)
class RequestOtpData:
    expires_at: datetime
    demo_otp: str | None


class RequestOtpHandler:
    def __init__(
        self,
        users_repo: UserRepository,
        otp_challenges_repo: OtpChallengeRepository,
        otp_service: OtpService,
        clock_service: ClockService,
        *,
        otp_ttl_seconds: int,
        include_demo_otp: bool,
    ) -> None:
        self._users_repo = users_repo
        self._otp_challenges_repo = otp_challenges_repo
        self._otp_service = otp_service
        self._clock_service = clock_service
        self._otp_ttl_seconds = otp_ttl_seconds
        self._include_demo_otp = include_demo_otp

    async def handle(self, command: RequestOtpCommand) -> Result[RequestOtpData]:
        email = command.email.strip().casefold()
        now = self._clock_service.now()
        proposed_user_id = uuid4()

        await self._users_repo.ensure_by_email(email, proposed_user_id, now)
        user = await self._users_repo.get_by_email_for_update(email)

        await self._otp_challenges_repo.invalidate_current_for_user(user.id, now)

        code = self._otp_service.generate_code()
        expires_at = now + timedelta(seconds=self._otp_ttl_seconds)
        await self._otp_challenges_repo.add(
            OtpChallenge(
                id=uuid4(),
                user_id=user.id,
                otp_digest=self._otp_service.digest(email, code),
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

The constructor receives `users_repo`, `otp_challenges_repo`, `otp_service`, `clock_service`, `otp_ttl_seconds`, and `include_demo_otp`, typed against the matching domain ports.

#### Package façade update

The Slice 1 `backend/app/domain/__init__.py` façade exports the public symbols below. Same-layer code may re-export through `entities/`, `ports/`, and `use_cases/` package façades; cross-layer imports still use `app.domain` only.

```python
from app.domain.entities.otp_challenge import OtpChallenge
from app.domain.entities.user import User
from app.domain.ports.repositories.otp_challenge_repository import (
    OtpChallengeRepository,
)
from app.domain.ports.repositories.user_repository import UserRepository
from app.domain.ports.services.clock_service import ClockService
from app.domain.ports.services.otp_service import OtpService
from app.domain.result import Result
from app.domain.use_cases.otp.request_otp_cmd import (
    RequestOtpCommand,
    RequestOtpData,
    RequestOtpHandler,
)

__all__ = [
    "ClockService",
    "OtpChallenge",
    "OtpChallengeRepository",
    "OtpService",
    "RequestOtpCommand",
    "RequestOtpData",
    "RequestOtpHandler",
    "Result",
    "User",
    "UserRepository",
]
```

### DB

Create `backend/app/db/session.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def build_session_factory(
    database_url: str,
) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)
```

Create `backend/app/db/models.py`. The first authentication migration includes all three tables; this slice uses only the user and OTP-challenge behavior.

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(UUIDType(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class OtpChallengeModel(Base):
    __tablename__ = "otp_challenges"
    __table_args__ = (
        CheckConstraint(
            "failed_attempt_count >= 0",
            name="ck_otp_challenges_failed_attempt_count_nonnegative",
        ),
        Index(
            "ix_otp_challenges_user_id_created_at",
            "user_id",
            text("created_at DESC"),
        ),
        Index(
            "uq_otp_challenges_one_current_per_user",
            "user_id",
            unique=True,
            postgresql_where=text(
                "consumed_at IS NULL AND invalidated_at IS NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    otp_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    failed_attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AuthSessionModel(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_id", "user_id"),
    )

    jti: Mapped[UUID] = mapped_column(UUIDType(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
```

“Current” deliberately ignores expiry and failed-attempt count. An expired or locked challenge remains current until it is consumed or invalidated, so request and verification can classify it correctly. The partial index guarantees at most one current row per user.

Create `User` and `OtpChallenge` domain/ORM mappers in `backend/app/db/mappers/user.py` and `backend/app/db/mappers/otp_challenge.py`. `backend/app/db/mappers/__init__.py` re-exports their `to_domain` and `to_model` functions with entity-qualified aliases.

Implement `backend/app/db/repositories/user_repository.py`:

1. `ensure_by_email` executes `INSERT INTO users (id, email, created_at) VALUES (:id, :email, :created_at) ON CONFLICT (email) DO NOTHING`.
2. `get_by_email_for_update` selects the complete `UserModel` where `email = :email` and applies `FOR UPDATE`.
3. The insert and select run in the same transaction. If another request is creating the same email, PostgreSQL waits for that insert to resolve; the subsequent row lock serializes challenge changes for that user.

Implement `OtpChallengeRepository` in `backend/app/db/repositories/otp_challenge_repository.py`:

- `invalidate_current_for_user` updates **all** rows for the user where both `consumed_at IS NULL` and `invalidated_at IS NULL`; do not filter by expiry or attempt count;
- execute the invalidation as an explicit SQL `UPDATE` before adding the replacement row, so the partial unique predicate is cleared first;
- `add` maps the domain entity to an ORM model and adds it to the session.

This lock order is mandatory for every OTP request: atomic user insert, lock user, execute the current-challenge invalidation, insert the new challenge, then return from the handler so the transaction context commits. The user lock plus partial unique index makes concurrent requests deterministic and prevents two current challenges.

Alembic belongs under `backend/` in this repository. Initialize it now:

```sh
cd backend
uv run alembic init alembic
```

Configure `backend/alembic/env.py` to import `Base` from `app.db`, set `target_metadata = Base.metadata`, use the async migration pattern, and obtain the URL from `get_settings().database_url`. Keep `backend/alembic.ini` beside `pyproject.toml`.

Generate, review, and apply the migration:

```sh
cd backend
uv run alembic revision --autogenerate -m "add authentication tables"
uv run alembic upgrade head
```

Confirm the generated revision contains `uq_otp_challenges_one_current_per_user` with `postgresql_where=sa.text("consumed_at IS NULL AND invalidated_at IS NULL")`. If autogenerate omits the predicate, add that `op.create_index` call over `["user_id"]` with `unique=True`.

The next implementation step is Slice 1 application composition in the API section below.

### API

Complete the composition prerequisites before making the request-OTP route runnable. They are part of the incoming-adapter stage because `backend/app/dependencies.py` composes the domain handler for an HTTP request; they do not move persistence or domain work out of the completed sections above.

#### Composition prerequisites

Create `backend/app/auth/system_clock.py` with `SystemClock`, which structurally implements `ClockService` and returns `datetime.now(UTC)`. It must return a timezone-aware UTC datetime.

Create `backend/app/auth/otp_service.py` with `HmacOtpService`:

- accept the configured `SecretStr` OTP HMAC secret without logging or retaining a displayable value;
- generate exactly six zero-padded digits with `secrets.randbelow(1_000_000)`;
- calculate lowercase hexadecimal `HMAC-SHA256(OTP_HMAC_SECRET, f"{normalized_email}:{code}")`;
- compare expected and submitted digests with `hmac.compare_digest`.

Complete the package façades before composing cross-layer collaborators:

```python
# backend/app/auth/__init__.py
from app.auth.otp_service import HmacOtpService
from app.auth.system_clock import SystemClock

__all__ = ["HmacOtpService", "SystemClock"]
```

```python
# backend/app/db/__init__.py
from app.db.models import Base
from app.db.repositories.otp_challenge_repository import (
    OtpChallengeRepositoryImpl,
)
from app.db.repositories.user_repository import UserRepositoryImpl
from app.db.session import AsyncSession, build_session_factory

__all__ = [
    "AsyncSession",
    "Base",
    "build_session_factory",
    "OtpChallengeRepositoryImpl",
    "UserRepositoryImpl",
]
```

Create `backend/app/dependencies.py`. It is the composition root: cross-layer imports come only from `app.auth`, `app.db`, and `app.domain`; each request-OTP execution creates one session and one `session.begin()` transaction context. `build_request_otp_handler` wires `SystemClock`, `HmacOtpService`, `UserRepositoryImpl`, `OtpChallengeRepositoryImpl`, and `RequestOtpHandler` using that shared session.

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

The builder enables demo output only when both conditions are true:

```python
include_demo_otp = (
    settings.app_env == "development" and settings.enable_demo_otp
)
```

Store the resolved settings and session factory on `app.state` in the app factory before a request can call this executor. Make session-factory engine ownership explicit and dispose every app-owned engine during lifespan shutdown; do not create an unmanaged engine for command sessions. Keep the existing live/ready health behavior.

The existing API scaffold is incomplete until it is updated as follows.

Complete `backend/app/api/schemas/errors.py`:

```python
from typing import Any

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
```

Complete `backend/app/api/result_mapping.py`:

```python
from typing import TypeVar, cast

from app.domain import Result

T = TypeVar("T")


class ApiResultError(Exception):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


def unwrap_result(result: Result[T]) -> T:
    if result.is_success:
        return cast("T", result.data)
    assert result.error_code is not None
    raise ApiResultError(result.error_code)
```

Complete `backend/app/api/exception_handlers.py`. This is the only error-code-to-HTTP mapping. Keep all mappings here now; codes that are not yet returned become reachable in their later slices.

```python
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.result_mapping import ApiResultError

ERROR_RESPONSES: dict[str, tuple[int, str]] = {
    "OTP_INVALID": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP is invalid.",
    ),
    "OTP_EXPIRED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP has expired.",
    ),
    "OTP_LOCKED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP is locked.",
    ),
    "OTP_CONSUMED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP has already been used.",
    ),
    "OTP_SUPERSEDED": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The OTP has been superseded.",
    ),
    "AUTHENTICATION_FAILED": (
        status.HTTP_401_UNAUTHORIZED,
        "Authentication failed.",
    ),
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": details or {},
        },
    )


async def handle_validation_error(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "Request validation failed.",
        {"errors": error.errors()},
    )


async def handle_api_result_error(
    _: Request, error: ApiResultError
) -> JSONResponse:
    mapped = ERROR_RESPONSES.get(error.error_code)
    if mapped is None:
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Internal server error.",
        )
    status_code, message = mapped
    return error_response(status_code, error.error_code, message)


async def handle_uncaught_exception(_: Request, __: Exception) -> JSONResponse:
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_ERROR",
        "Internal server error.",
    )
```

`unwrap_result` never copies, exposes, or logs `Result.reason`. It runs only after a transactional command executor returns, so the transaction is already committed before a failed result becomes an API-layer exception. Routes retain their explicit `201` request-OTP, `200` verify/health, and `204` logout statuses.

Complete these Pydantic DTOs in `backend/app/api/schemas/auth.py`:

```python
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RequestOtpRequest(BaseModel):
    email: EmailStr


class RequestOtpResponse(BaseModel):
    expires_at: datetime
    otp: str | None = Field(default=None)
```

Complete `backend/app/api/routers/auth.py` with the request-OTP route:

```python
from fastapi import APIRouter, Request, status

from app.api.result_mapping import unwrap_result
from app.api.schemas.auth import RequestOtpRequest, RequestOtpResponse
from app.dependencies import execute_request_otp
from app.domain import RequestOtpCommand

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/otp/request",
    status_code=status.HTTP_201_CREATED,
    response_model=RequestOtpResponse,
    response_model_exclude_none=True,
)
async def request_otp(
    payload: RequestOtpRequest,
    request: Request,
) -> RequestOtpResponse:
    result = await execute_request_otp(
        request,
        RequestOtpCommand(email=str(payload.email)),
    )
    data = unwrap_result(result)
    assert data is not None
    return RequestOtpResponse(
        expires_at=data.expires_at,
        otp=data.demo_otp,
    )
```

The last setting is mandatory: when demo output is disabled, `otp` is omitted rather than serialized as `null`. Never log request-OTP response bodies.

#### Package façade update

At the end of this API section, complete `backend/app/api/__init__.py`:

```python
from app.api.exception_handlers import (
    handle_api_result_error,
    handle_uncaught_exception,
    handle_validation_error,
)
from app.api.routers.auth import router as auth_router

__all__ = [
    "auth_router",
    "handle_api_result_error",
    "handle_uncaught_exception",
    "handle_validation_error",
]
```

Only after the API façade, router, and handlers exist, update `backend/app/main.py`:

- register `auth_router`;
- register `handle_validation_error`, `handle_api_result_error`, and `handle_uncaught_exception` for their respective exception types;
- configure CORS by splitting `settings.cors_allowed_origins` on commas, trimming whitespace, and discarding empty origins;
- preserve the app's settings/session-factory state and dispose all app-owned database engines during shutdown.

### UI

After the API is runnable, add `frontend/src/types/auth.ts`:

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

### Domain

Create `backend/app/domain/error_codes.py`:

```python
OTP_INVALID = "OTP_INVALID"
OTP_EXPIRED = "OTP_EXPIRED"
OTP_LOCKED = "OTP_LOCKED"
OTP_CONSUMED = "OTP_CONSUMED"
OTP_SUPERSEDED = "OTP_SUPERSEDED"
AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
```

Create `backend/app/domain/entities/auth_session.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthSession:
    jti: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
```

Create `backend/app/domain/token_claims.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: UUID
    session_jti: UUID
    expires_at: datetime
```

Create `VerifyOtpCommand(email: str, otp: str)`, `VerifyOtpData(access_token: str, expires_at: datetime)`, and `VerifyOtpHandler` in `backend/app/domain/use_cases/otp/verify_otp_cmd.py`.

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
    now = self._clock_service.now()
    user = await self._users_repo.get_by_email_for_update(email)
    if user is None:
        return Result.failure(OTP_INVALID)

    current = await self._otp_challenges_repo.get_current_for_user_for_update(
        user.id
    )
    submitted_digest = self._otp_service.digest(email, command.otp)
    matching = (
        await self._otp_challenges_repo.get_newest_by_digest_for_update(
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
        await self._otp_challenges_repo.mark_consumed(matching.id, now)
        await self._auth_sessions_repo.add(
            AuthSession(
                jti=session_jti,
                user_id=user.id,
                expires_at=token_expires_at,
                revoked_at=None,
                created_at=now,
            )
        )
        access_token = self._token_service.encode(
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
    await self._otp_challenges_repo.set_failed_attempt_count(
        current.id, new_count
    )
    if new_count >= self._otp_max_attempts:
        return Result.failure(OTP_LOCKED)
    return Result.failure(OTP_INVALID)
```

The constructor receives `users_repo`, `otp_challenges_repo`, `auth_sessions_repo`, `otp_service`, `token_service`, `clock_service`, `otp_max_attempts`, and `access_token_ttl_minutes`, typed against the matching domain ports. The handler imports only domain entities, result/error definitions, and ports. Truncating the token expiry to whole seconds before both session persistence and JWT encoding keeps the database value equal to the integer JWT `exp`.

#### File updates

At the end of this Domain section, create `backend/app/domain/ports/services/token_service.py`:

```python
from uuid import UUID

from app.domain.result import Result
from app.domain.token_claims import TokenClaims


class TokenService(Protocol):
    def encode(
        self, user_id: UUID, session_jti: UUID, expires_at: datetime
    ) -> str: ...

    def decode(self, token: str) -> Result[TokenClaims]: ...
```

Alter `backend/app/domain/ports/repositories/user_repository.py`:

```python
async def get_by_email_for_update(self, email: str) -> User | None: ...
```

Alter `backend/app/domain/ports/repositories/otp_challenge_repository.py`:

```python
async def get_current_for_user_for_update(
    self, user_id: UUID
) -> OtpChallenge | None: ...

async def get_newest_by_digest_for_update(
    self, user_id: UUID, digest: str
) -> OtpChallenge | None: ...

async def set_failed_attempt_count(
    self, challenge_id: UUID, count: int
) -> None: ...

async def mark_consumed(
    self, challenge_id: UUID, consumed_at: datetime
) -> None: ...
```

Create `backend/app/domain/ports/repositories/auth_session_repository.py`:

```python
from typing import Protocol

from app.domain.entities.auth_session import AuthSession


class AuthSessionRepository(Protocol):
    async def add(self, session: AuthSession) -> None: ...
```

#### Package façade update

At the end of this Domain section, alter `backend/app/domain/__init__.py`:

```python
from app.domain.entities.auth_session import AuthSession
from app.domain.error_codes import (
    AUTHENTICATION_FAILED,
    OTP_CONSUMED,
    OTP_EXPIRED,
    OTP_INVALID,
    OTP_LOCKED,
    OTP_SUPERSEDED,
)
from app.domain.ports.repositories.auth_session_repository import (
    AuthSessionRepository,
)
from app.domain.ports.services.token_service import TokenService
from app.domain.token_claims import TokenClaims
from app.domain.use_cases.otp.verify_otp_cmd import (
    VerifyOtpCommand,
    VerifyOtpData,
    VerifyOtpHandler,
)

__all__ += [
    "AUTHENTICATION_FAILED",
    "AuthSession",
    "AuthSessionRepository",
    "OTP_CONSUMED",
    "OTP_EXPIRED",
    "OTP_INVALID",
    "OTP_LOCKED",
    "OTP_SUPERSEDED",
    "TokenClaims",
    "TokenService",
    "VerifyOtpCommand",
    "VerifyOtpData",
    "VerifyOtpHandler",
]
```

### DB

Implement challenge lookups with SQLAlchemy `select(OtpChallengeModel).with_for_update()`:

- lock the user by normalized email first;
- query current by `user_id` and the two null status columns only;
- query matching by `user_id` and exact digest across all statuses, ordered by `created_at DESC, id DESC`;
- map rows to domain entities;
- use explicit `UPDATE` statements for attempt count and consumption.

The user row lock serializes request and verify operations for one identity. The challenge row locks protect against accidental callers that bypass that convention. Do not combine current-state filters with expiry or attempt filters because doing so loses the distinction between expired, locked, and invalid.

Create `backend/app/db/repositories/auth_session_repository.py` with `AuthSessionRepositoryImpl` and add the `AuthSession` mapper under `backend/app/db/mappers/auth_session.py`, re-exported from `backend/app/db/mappers/__init__.py`. No migration change is required because `auth_sessions` was created in Slice 1.

Implement `PyJwtTokenService` in `backend/app/auth/jwt_service.py`:

- encode HS256 with string `sub`, string `jti`, and integer `exp` from `int(expires_at.timestamp())`;
- decode with `algorithms=["HS256"]` and options requiring `sub`, `jti`, and `exp`;
- require `sub` and `jti` to be strings, reject booleans/non-integers for `exp`, convert UUIDs and UTC expiry inside the guarded block;
- catch `jwt.PyJWTError`, `KeyError`, `TypeError`, `ValueError`, and `OverflowError`;
- translate every decode or claim-conversion failure to `Result.failure(AUTHENTICATION_FAILED, reason=error)`;
- return `Result.success(TokenClaims(...))` for valid claims and never leak PyJWT exceptions.

Implement `build_verify_otp_handler` and `execute_verify_otp` in `backend/app/dependencies.py`. Compose `PyJwtTokenService`, `UserRepositoryImpl`, `OtpChallengeRepositoryImpl`, `AuthSessionRepositoryImpl`, and `VerifyOtpHandler` inside one session transaction. Import those cross-layer symbols from `app.auth`, `app.db`, and `app.domain`.

#### Package façade updates

At the end of this DB section, alter `backend/app/db/__init__.py`:

```python
from app.db.repositories.auth_session_repository import (
    AuthSessionRepositoryImpl,
)

__all__ += ["AuthSessionRepositoryImpl"]
```

Alter `backend/app/auth/__init__.py`:

```python
from app.auth.jwt_service import PyJwtTokenService

__all__ += ["PyJwtTokenService"]
```

### API

The central error mapping completed in Slice 1 already maps `OTP_INVALID`, `OTP_EXPIRED`, `OTP_LOCKED`, `OTP_CONSUMED`, and `OTP_SUPERSEDED` to `422` and their safe client messages. Do not add a route-local mapping.

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

At the end of this API section, alter `backend/app/api/routers/auth.py`:

```python
from app.api.schemas.auth import (
    # previous DTOs ...
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.dependencies import (
    # previous executor ...
    execute_verify_otp,
)
from app.domain import VerifyOtpCommand


@router.post(
    "/otp/verify",
    status_code=status.HTTP_200_OK,
    response_model=VerifyOtpResponse,
)
async def verify_otp(
    payload: VerifyOtpRequest,
    request: Request,
) -> VerifyOtpResponse:
    result = await execute_verify_otp(
        request,
        VerifyOtpCommand(email=str(payload.email), otp=payload.otp),
    )
    data = unwrap_result(result)
    assert data is not None
    return VerifyOtpResponse(
        access_token=data.access_token,
        expires_at=data.expires_at,
    )
```

No Bearer credential is required for either OTP route. Do not expose JWT or OTP values in logs.

All five OTP failure outcomes use `ErrorEnvelope` and the error-code constants created in this slice's Domain section.

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

### Domain

Create `backend/app/domain/current_user.py`:

```python
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    email: str
    session_jti: UUID
```

Create `backend/app/domain/ports/current_user_provider.py`:

```python
from typing import Protocol

from app.domain.current_user import CurrentUser


class CurrentUserProvider(Protocol):
    def get(self) -> CurrentUser: ...
```

`CurrentUser` is the value; `CurrentUserProvider` is the behavior. Domain code never sets the provider and never imports `ContextVar` or the API implementation. Only handlers that require an authenticated HTTP principal receive this port.

Alter `backend/app/domain/ports/repositories/auth_session_repository.py`:

```python
from uuid import UUID

from app.domain.entities.auth_session import AuthSession


async def get_by_jti(self, jti: UUID) -> AuthSession | None: ...
```

Alter `backend/app/domain/ports/repositories/user_repository.py`:

```python
async def get_by_id(self, user_id: UUID) -> User | None: ...
```

Create `GetCurrentUserQuery(token: str)` and `GetCurrentUserHandler` in `backend/app/domain/use_cases/user/get_current_user_query.py`. The handler depends only on `token_service`, `clock_service`, `auth_sessions_repo`, and `users_repo`, typed against the matching domain ports:

```python
async def handle(self, query: GetCurrentUserQuery) -> Result[CurrentUser]:
    claims_result = self._token_service.decode(query.token)
    if not claims_result.is_success:
        return Result.failure(
            AUTHENTICATION_FAILED,
            reason=claims_result.reason,
        )
    claims = claims_result.data
    assert claims is not None

    now = self._clock_service.now()
    session = await self._auth_sessions_repo.get_by_jti(claims.session_jti)
    if session is None:
        return Result.failure(AUTHENTICATION_FAILED)
    if session.user_id != claims.user_id:
        return Result.failure(AUTHENTICATION_FAILED)
    if session.revoked_at is not None or session.expires_at <= now:
        return Result.failure(AUTHENTICATION_FAILED)
    if session.expires_at != claims.expires_at:
        return Result.failure(AUTHENTICATION_FAILED)

    user = await self._users_repo.get_by_id(claims.user_id)
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

#### Package façade update

At the end of this Domain section, alter `backend/app/domain/__init__.py`:

```python
from app.domain.current_user import CurrentUser
from app.domain.ports.current_user_provider import CurrentUserProvider
from app.domain.use_cases.user.get_current_user_query import (
    GetCurrentUserHandler,
    GetCurrentUserQuery,
)

__all__ += [
    "CurrentUser",
    "CurrentUserProvider",
    "GetCurrentUserHandler",
    "GetCurrentUserQuery",
]
```

### DB

Extend `AuthSessionRepositoryImpl` in `backend/app/db/repositories/auth_session_repository.py` with the session query operation, and extend `UserRepositoryImpl` in `backend/app/db/repositories/user_repository.py` with the user query operation:

- session lookup selects by primary-key `jti` without hiding revoked or expired rows; the domain query performs the active-state decision;
- user lookup selects the fresh user by primary key;
- both return domain entities and never expose ORM models to the handler.

Keep the server-side session check even though PyJWT validates `exp`: logout and administrative revocation are database state, and the JWT alone cannot represent them.

Application composition for the current-user query belongs with the API binding work below: create the shared `ContextVarCurrentUserProvider` first, then wire the short-lived read executor that uses it.

### API

The central error mapping completed in Slice 1 already maps `AUTHENTICATION_FAILED` to `401` with its safe client message. Do not add a route-local mapping.

Create `backend/app/api/current_user_provider.py`:

```python
from contextvars import ContextVar, Token

from app.domain import CurrentUser


class ContextVarCurrentUserProvider:
    def __init__(self) -> None:
        self._current_user: ContextVar[CurrentUser] = ContextVar(
            "current_user"
        )

    def bind(self, current_user: CurrentUser) -> Token[CurrentUser]:
        return self._current_user.set(current_user)

    def reset(self, token: Token[CurrentUser]) -> None:
        self._current_user.reset(token)

    def get(self) -> CurrentUser:
        try:
            return self._current_user.get()
        except LookupError as error:
            raise RuntimeError("No current user is bound.") from error
```

It structurally implements the domain `CurrentUserProvider.get() -> CurrentUser` port and adds adapter-only `bind(current_user)` and `reset(token)` operations.

Create one provider instance in application composition and reuse that instance for request binding and handler injection. The stored value is task-local request context, not a process-global mutable user.

In `backend/app/dependencies.py`, add:

- a module-level `ContextVarCurrentUserProvider` instance;
- `get_current_user_provider()` that returns that same instance;
- `build_get_current_user_handler(session)` that wires `PyJwtTokenService`, `SystemClock`, `AuthSessionRepositoryImpl`, `UserRepositoryImpl`, and `GetCurrentUserHandler`;
- `execute_get_current_user(request, query)` that opens one short-lived `AsyncSession` from `request.app.state.session_factory`, invokes the handler, and closes the session without committing. Any implicit read transaction rolls back on close.

`GetCurrentUserExecutor` is the callable type of that executor. Expose it to FastAPI through `get_current_user_executor`, which returns `execute_get_current_user` (or an equivalent callable bound to app state).

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

Create `backend/app/api/routers/health.py`:

```python
from fastapi import APIRouter, Depends

from app.api.dependencies import bind_current_user

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "/authenticated",
    dependencies=[Depends(bind_current_user)],
)
async def health_authenticated() -> dict[str, str]:
    return {"status": "ok"}
```

Register the health router in `backend/app/main.py`. The endpoint returns `200 {"status":"ok"}` only after the complete current-user query succeeds and its result is bound for the request.

#### Package façade update

At the end of this API section, alter `backend/app/api/__init__.py`:

```python
from app.api.routers.health import router as health_router

__all__ += ["health_router"]
```

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

### Domain

Create fieldless `LogoutCommand` and `LogoutHandler` in `backend/app/domain/use_cases/auth_session/logout_cmd.py`.

The exact handler is:

```python
async def handle(self, command: LogoutCommand) -> Result[None]:
    current_user = self._current_user_provider.get()
    changed = await self._auth_sessions_repo.revoke(
        current_user.session_jti, self._clock_service.now()
    )
    if not changed:
        return Result.failure(AUTHENTICATION_FAILED)
    return Result.success()
```

The handler depends on `current_user_provider`, `auth_sessions_repo`, and `clock_service`, typed against the matching domain ports. The provider is a constructor dependency, not a global import. The handler revokes one `jti`; it never updates every session belonging to the user.

#### File update

At the end of this Domain section, add this method to `AuthSessionRepository` in `backend/app/domain/ports/repositories/auth_session_repository.py`:

```python
async def revoke(self, jti: UUID, revoked_at: datetime) -> bool: ...
```

#### Package façade update

At the end of this Domain section, alter `backend/app/domain/__init__.py`:

```python
from app.domain.use_cases.auth_session.logout_cmd import (
    LogoutCommand,
    LogoutHandler,
)

__all__ += ["LogoutCommand", "LogoutHandler"]
```

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

Implement `build_logout_handler` and `execute_logout` in `backend/app/dependencies.py` using the shared `ContextVarCurrentUserProvider` instance, `AuthSessionRepositoryImpl`, and the shared `SystemClock`. `LogoutExecutor` is the callable type of that executor; expose it through `get_logout_executor`. The API authentication dependency and logout executor may use separate short-lived database sessions; the former binds `CurrentUser`, while the guarded update makes the command safe if revocation occurs between those operations.

### API

At the end of this API section, alter `backend/app/api/routers/auth.py`:

```python
from typing import Annotated

from fastapi import Depends, Response

from app.api.dependencies import bind_current_user
from app.dependencies import LogoutExecutor, get_logout_executor
from app.domain import LogoutCommand


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

### UI

Add `logout()` to `frontend/src/api/client.ts`. It sends an authenticated `POST /auth/logout` with no body.

When the user clicks **Logout**:

- on `204`, remove `access_token`, clear all authentication UI state, and show the email form;
- on `401`, the shared client removes the token, then the UI shows the email form;
- on a network or `5xx` error, keep the token and show a retryable error because server-side revocation is unknown.

Create two independent browser sessions or obtain two tokens for the same email. Log out with token A, then prove token A receives `401` while token B still receives `200`.

## Final verification

Prerequisites: PostgreSQL is healthy, the reviewed Slice 1 Alembic revision is applied, the backend runs on port 8000, and the frontend runs on port 5173. Structural milestones already complete (Slice 0 configuration, Slice 1 domain, and Slice 1 persistence/migration) do not need re-implementation; the checklist below verifies end-to-end behavior after Slice 1 composition/API/UI and Slices 2–4 are finished.

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
