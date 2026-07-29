# Python / FastAPI learning notes

Notes from working through layers in this project.

---

## Authentication system design

### `GetCurrentUserExecutor` — reading the brackets

File: `backend/app/api/dependencies.py`

```python
GetCurrentUserExecutor = Callable[
    [GetCurrentUserQuery], Awaitable[Result[CurrentUser]]
]
```

Read it **from the inside out**:

| Piece | Meaning |
|---|---|
| `CurrentUser` | Domain object: authenticated user |
| `Result[CurrentUser]` | Success with a user, or failure with an error code |
| `Awaitable[...]` | You must `await` it — it's async |
| `[GetCurrentUserQuery]` | One argument: the query object (holds the JWT token) |
| `Callable[[...], ...]` | "A function you can call" |

In plain English:

> **A callable that takes a `GetCurrentUserQuery` and, when awaited, returns `Result[CurrentUser]`.**

That matches the inner function in `get_current_user_executor`:

```python
async def execute(query: GetCurrentUserQuery) -> Result[CurrentUser]:
    async with request.app.state.session_factory() as session:
        handler = build_get_current_user_handler(session, request.app.state.settings)
        return await handler.handle(query)
```

`Callable` always uses **two** bracket groups:

```python
Callable[[arg1_type, arg2_type], return_type]
#         ^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^
#         "what you pass in"        "what you get back"
```

Why not just write `async def ...` inline? The alias names the **shape** of the injected dependency so `bind_current_user` can declare `executor: GetCurrentUserExecutor` without repeating the full generic.

---

### `bind_current_user` — where do those parameters come from?

File: `backend/app/api/dependencies.py`

They are **not** passed by the HTTP client. FastAPI builds them via **dependency injection**: it inspects the function signature and resolves each `Depends(...)` before your route runs.

```python
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
    ...
    token = provider.bind(current_user)
    try:
        yield
    finally:
        provider.reset(token)
```

Resolution chain:

```
HTTP request
    │
    ├─► bearer_scheme (HTTPBearer)        → parses Authorization: Bearer <token>
    │                                          → credentials (or None)
    │
    ├─► get_current_user_executor(Request)  → returns the async execute() closure
    │                                          (with session/request wired in)
    │
    └─► get_current_user_provider()         → singleton ContextVarCurrentUserProvider
```

What the function does:

1. Reject missing/non-Bearer auth.
2. Call `executor(GetCurrentUserQuery(token=...))` to validate JWT + session.
3. `provider.bind(current_user)` — store user in a `ContextVar` for this request.
4. **`yield`** — hand off to the route handler (or next dependency).
5. **`finally: provider.reset(token)`** — clean up after the request.

The `yield` makes this a **generator dependency**: code before `yield` runs on the way in; code after (here, in `finally`) runs on the way out. That's why the return type is `AsyncIterator[None]` — it yields nothing useful; the side effect (bind/reset) is the point.

`HTTPBearer(auto_error=False)` means a missing header does **not** auto-raise 401; this function checks credentials itself and maps failure through the domain `Result`.

---

### `Annotated[..., Depends(...)]` — what's going on?

File: `backend/app/api/dependencies.py`

Two layers in one annotation:

```python
credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
#                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^^
#                      real Python type (for type checkers)   FastAPI metadata (how to inject)
```

Older equivalent:

```python
credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)
```

Same behavior; `Annotated` keeps **type** and **injection rule** separate — better for mypy/pyright and the modern FastAPI style.

FastAPI reads `Depends(...)` and knows: "Don't take this from the query/body/path — call this function (or use this security scheme) to produce the value."

Nested `Depends` also chains: `get_current_user_executor` needs `Request`; FastAPI injects `Request` into it automatically because `Request` is a known special parameter.

---

### `dependencies=[Depends(bind_current_user)]` on a route

From `backend/app/api/routers/health.py`:

```python
@router.get(
    "/authenticated",
    dependencies=[Depends(bind_current_user)],
)
async def health_authenticated() -> dict[str, str]:
    return {"status": "ok"}
```

This attaches `bind_current_user` at the **route decorator** level.

Two ways to use a dependency in FastAPI:

| Style | Example | Effect |
|---|---|---|
| Parameter | `async def foo(user: CurrentUser = Depends(...))` | Runs dependency **and** passes return value into the handler |
| Route `dependencies=` | `dependencies=[Depends(bind_current_user)]` | Runs dependency **only**; return value is **not** passed to the handler |

Here the handler doesn't need `CurrentUser` in its signature — it only needs auth to succeed. If auth fails, `unwrap_result` raises before the handler runs. If it passes, the handler returns `{"status": "ok"}`.

Flow:

```
GET /health/authenticated + Authorization: Bearer ...
        │
        ▼
bind_current_user runs (before handler)
        │ validate token, bind user to ContextVar
        ▼
health_authenticated() runs
        │
        ▼
bind_current_user cleanup (finally: reset ContextVar)
        │
        ▼
response sent
```

`/health/live` has **no** such dependency — no auth required.

---

### `POST /auth/logout` — two `Depends` on one route

File: `backend/app/api/routers/auth.py`

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

This route uses **two** dependency mechanisms. They look similar but do different jobs.

| # | Where | Dependency | What it does |
|---|---|---|---|
| 1 | `dependencies=[Depends(bind_current_user)]` on the decorator | Auth gate + request context | Validates Bearer token, loads `CurrentUser`, stores it in a `ContextVar`, cleans up in `finally` |
| 2 | `executor: Annotated[..., Depends(get_logout_executor)]` on the handler parameter | Command executor | Returns the async closure that opens a DB transaction and runs `LogoutHandler` |

#### Why not one `Depends`?

Each dependency answers a different question:

- **`bind_current_user`** — *"Is this request authenticated, and who is the caller?"*
- **`get_logout_executor`** — *"How do I run the logout command for this HTTP request?"*

They must run in order: auth and binding happen **before** the handler body. The handler then calls `executor(LogoutCommand())`, and the domain handler reads `session_jti` through `CurrentUserProvider.get()` — not from a route parameter.

That separation is intentional hexagonal design: the route never sees `CurrentUser`, `session_jti`, or the raw JWT. Auth binding is an incoming-adapter concern; command execution is composition wiring.

#### Why `bind_current_user` is on the decorator, not a parameter

`bind_current_user` yields `None` — its value is useless to the handler. The handler only needs the **side effect** (user bound in the `ContextVar`).

Putting it in `dependencies=[...]` on the decorator:

- runs it as a gate before the handler;
- avoids a dummy parameter like `_auth: Annotated[None, Depends(bind_current_user)]`;
- matches `/health/authenticated`, which uses the same pattern.

`get_logout_executor` **does** produce something the handler uses (the callable), so it belongs as a **parameter** dependency.

#### Execution order

```
POST /auth/logout + Authorization: Bearer ...
        │
        ▼
bind_current_user (route dependency)
        │ parse Bearer → validate JWT + session
        │ provider.bind(current_user)  ← LogoutHandler reads this later
        ▼
get_logout_executor (parameter dependency)
        │ returns execute() closure wired to Request + session_factory
        ▼
logout() handler body
        │ executor(LogoutCommand())
        │   └─► build_logout_handler(..., get_current_user_provider())
        │       └─► LogoutHandler.handle() → revoke session_jti
        ▼
bind_current_user finally: provider.reset()
        │
        ▼
204 No Content
```

Note: `bind_current_user` and `get_logout_executor` each open their **own** short-lived DB session. That is safe here because logout uses a guarded `UPDATE` (`revoked_at IS NULL AND expires_at > :now`); even if auth read and revoke write are separate transactions, the write still fails cleanly when the session is already invalid.

#### Compared to OTP routes

`/auth/otp/request` and `/auth/otp/verify` have **no** auth dependency — they are public. Only logout (and authenticated health) combine route-level auth binding with handler-level executors.

---

### Big picture

```mermaid
flowchart TD
    A[HTTP Request] --> B[Depends bind_current_user]
    B --> C[bearer_scheme → credentials]
    B --> D[get_current_user_executor → execute fn]
    B --> E[get_current_user_provider → ContextVar]
    C --> F{valid Bearer?}
    F -->|no| G[401 via unwrap_result]
    F -->|yes| H[executor validates JWT]
    H --> I[provider.bind user]
    I --> J[route handler]
    J --> K[provider.reset]
```

**Summary:**

- `GetCurrentUserExecutor` = "async function(query) → Result[user]".
- `bind_current_user`'s parameters come from FastAPI's DI, not the client.
- `Annotated[..., Depends(...)]` splits type vs injection.
- `dependencies=[...]` on the route runs auth as a gate without adding parameters to the handler.
- Logout uses **two** dependencies: decorator-level `bind_current_user` (auth + ContextVar side effect) and parameter-level `get_logout_executor` (injected command runner).
