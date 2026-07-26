# Phase 1 — Scaffolding

Bootstrap the Python backend, Vite/React frontend, PostgreSQL Compose service, configuration skeleton, and health endpoints so both dev servers hot-reload and quality checks pass on an empty project.

Canonical requirements live in [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md), [CONFIGURATION.md](../CONFIGURATION.md), and [API_CONTRACT.md](../API_CONTRACT.md). Run every command from the repository root unless noted.

## Done when

PostgreSQL is healthy, backend and frontend hot-reload, `/health/live` and `/health/ready` behave as documented, `yarn install --immutable` installs packages under `frontend/node_modules`, ruff/mypy/frontend typecheck pass, and the backend can open and close an async PostgreSQL connection.

## Steps

- [ ] Initialize the Python application with `uv` and pin Python 3.14.

```sh
uv init --app --python 3.14
```

- [ ] Add backend runtime dependencies.

```sh
uv add fastapi "uvicorn[standard]" pydantic pydantic-settings sqlalchemy asyncpg alembic pyjwt email-validator
```

- [ ] Add backend development dependencies.

```sh
uv add --dev ruff mypy pytest pytest-asyncio httpx "testcontainers[postgres]"
```

- [ ] Configure ruff and strict mypy in `pyproject.toml` (merge into the existing file).

```toml
[tool.ruff]
target-version = "py314"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.mypy]
python_version = "3.14"
strict = true
```

- [ ] Create backend package directories and keep them importable.

```sh
mkdir -p app tests/unit tests/integration scripts
touch app/__init__.py
```

- [ ] Enable Corepack and scaffold the Vite React TypeScript frontend.

```sh
corepack enable
yarn create vite frontend --template react-ts
```

- [ ] Configure Yarn for `node-modules`, install frontend dependencies, and add routing/testing packages.

```sh
cd frontend
corepack use yarn@stable
printf 'nodeLinker: node-modules\n' > .yarnrc.yml
yarn install
yarn add react-router-dom
yarn add -D vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
cd ..
```

- [ ] Add frontend lint, typecheck, and test scripts to `frontend/package.json` (merge into the existing `"scripts"` block).

```json
"lint": "eslint .",
"typecheck": "tsc --noEmit",
"test": "vitest --environment jsdom",
"test:run": "vitest run --environment jsdom"
```

- [ ] Verify immutable frontend installs resolve under `frontend/node_modules`.

```sh
cd frontend && yarn install --immutable && cd ..
```

- [ ] Add `.gitignore` entries for local secrets, Python artifacts, and frontend build output.

```sh
cat <<'EOF' >> .gitignore
.env
.venv/
__pycache__/
*.py[cod]
.mypy_cache/
.ruff_cache/
.pytest_cache/
frontend/node_modules/
frontend/dist/
EOF
```

- [ ] Add `.env.example` with development-safe placeholders matching [CONFIGURATION.md](../CONFIGURATION.md).

```sh
cat <<'EOF' > .env.example
APP_ENV=development
POSTGRES_DB=pg_db
POSTGRES_USER=pg_user
POSTGRES_PASSWORD=change-me-local-password
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://pg_user:change-me-local-password@127.0.0.1:5432/pg_db
JWT_SECRET=change-me-jwt-secret-at-least-32-bytes-long
OTP_HMAC_SECRET=change-me-otp-hmac-secret-at-least-32-bytes
ADMIN_API_KEY=x_admin_key
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173
LOG_LEVEL=INFO
EOF
```

`DATABASE_URL` is the connection string the backend uses to reach PostgreSQL. Keep its parts aligned with the `POSTGRES_*` variables above.

| Part | Value | Meaning |
| --- | --- | --- |
| Scheme | `postgresql+asyncpg://` | PostgreSQL database, accessed through SQLAlchemy's async driver `asyncpg` (not sync `psycopg2`). |
| Username | `pg_user` | DB login user; must match `POSTGRES_USER`. |
| Password | `change-me-local-password` | User password; must match `POSTGRES_PASSWORD`. |
| Host | `127.0.0.1` | Machine where Postgres runs — localhost because Compose publishes the port to your host. |
| Port | `5432` | Host port Postgres listens on; must match `POSTGRES_PORT`. |
| Database | `pg_db` | Database name to connect to; must match `POSTGRES_DB`. |

Full form: `postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>`

- [ ] Copy `.env.example` to a gitignored `.env` and replace placeholder secrets with local values.

```sh
cp .env.example .env
```

- [ ] Add Docker Compose with one PostgreSQL service (pinned image, volume, health check, development port).

```sh
cat <<'EOF' > docker-compose.yml
services:
  postgres:
    image: postgres:18.4-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "${POSTGRES_PORT}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 5s

volumes:
  postgres_data:
EOF
```

- [ ] Start PostgreSQL and confirm the container reaches `healthy`.

```sh
docker compose up -d postgres
docker compose ps
```

- [ ] Add `app/config.py` with `pydantic-settings` loading the [CONFIGURATION.md](../CONFIGURATION.md) variables.

```sh
cat <<'EOF' > app/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str
    database_url: str
    jwt_secret: str
    otp_hmac_secret: str
    admin_api_key: str | None = None
    cors_allowed_origins: str = "http://127.0.0.1:5173"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
EOF
```

- [ ] Add a minimal FastAPI app factory with `/health/live` and `/health/ready` (ready checks PostgreSQL).

```sh
cat <<'EOF' > app/main.py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    engine: AsyncEngine = create_async_engine(resolved.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(title="Wallet Sample", lifespan=lifespan)

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, str] | JSONResponse:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ok"}

    return app
EOF
```

- [ ] Add a minimal React shell (the Vite template default is enough for this phase).

```sh
test -f frontend/src/main.tsx
```

- [ ] Add frontend API base URL for local development.

```sh
printf 'VITE_API_BASE_URL=http://127.0.0.1:8000\n' > frontend/.env
```

- [ ] Start the backend development server.

```sh
uv run uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

- [ ] In a second terminal, start the frontend development server.

```sh
cd frontend && yarn dev
```

- [ ] Verify backend quality gates.

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
```

- [ ] Verify frontend quality gates.

```sh
cd frontend && yarn lint && yarn typecheck && yarn test:run
```

- [ ] Verify health endpoints and async PostgreSQL connectivity (backend must be running).

```sh
curl -sS http://127.0.0.1:8000/health/live
curl -sS http://127.0.0.1:8000/health/ready
```

Expected: both return HTTP 200 with `{"status":"ok"}` once PostgreSQL is healthy and `.env` `DATABASE_URL` matches Compose credentials.
