# Phase 4 — User live status with SSE and Wallet UI

Give users secure live transaction-status notifications over Server-Sent Events, with reconnect, resume, and authoritative snapshot reconciliation — replacing Phase 3's manual refresh on the Wallet page.

Work in this order:

1. `notifier-decision-and-domain`
2. `db-and-notifier-adapter`
3. `sse-endpoint`
4. `ui-streaming-client`
5. `smoke-check`

## Current implementation status

- **Not started.** Phase 3 is complete: all four mutations return `202` with `request_id`, the worker processes all types with duplicate safety, `GET /me/transactions` is the authoritative user snapshot exposing all Version 2 lifecycle fields, and the UI reconciles submissions by `request_id` via authoritative refresh.

Canonical behavior is defined by [API_CONTRACT.md](../v2/API_CONTRACT.md) §`GET /me/stream`, [TECHNICAL_REQUIREMENTS.md](../v2/TECHNICAL_REQUIREMENTS.md) §12/§13, [CONFIGURATION.md](../v2/CONFIGURATION.md) §8, and [IMPLEMENTATION_STEPS.md](../v2/IMPLEMENTATION_STEPS.md) §Phase 4.

## Purpose

Users receive secure live status notifications, recover from missed or repeated events through authoritative snapshots, and see correct balances and safe outcomes — while SSE remains a notification channel, never a source of truth.

## Prerequisites

- [ ] The transfer hard stop gate (Phase 3, Slice 4) is green.
- [ ] `GET /me/transactions` exposes `request_id`, `status`, `error`, `updated_at` and ownership filtering including incoming transfers.
- [ ] The notifier mechanism has been evaluated for correctness under the intended API replica topology (Step 1 records the decision).

## Scope

### In scope

- Status-notification domain port and framework-free event read model.
- Database-backed notifier adapter with resumable opaque event IDs.
- Authenticated `GET /me/stream` SSE endpoint with heartbeat, `Last-Event-ID` resume, and clean disconnect handling.
- Frontend authenticated streaming client (Bearer header, SSE framing, reconnect, reconciliation) and Wallet page live-status integration.

### Out of scope

- Admin live updates (admin long polling is Phase 5; admin never uses SSE or Kafka reads).
- A Kafka status topic (explicit non-goal for Version 2).
- WebSockets.

## Done when

Users receive secure live status notifications, recover from missed or repeated events through authoritative snapshots, and see correct balances and safe outcomes; a forced disconnect/reconnect across rapid status changes reconciles to the PostgreSQL snapshot with no regression or cross-user disclosure.

## Architecture rules

- SSE is a notification channel; PostgreSQL remains authoritative; the UI reconciles from `GET /me/transactions` after every connect and reconnect.
- Authentication is enforced before streaming, and every database selection used by the stream is scoped to the authenticated user — a client never receives another user's transaction status.
- Events carry only `{request_id, status, error?}` plus an opaque event ID; heartbeats are non-semantic comments; no JWTs, emails, or payload data on the wire.
- Once the `200` SSE response has started, failures close the connection — never append a JSON error envelope to the stream.
- Monotonic client reconciliation: upsert by `request_id`, compare `updated_at` from snapshots, ignore status regressions, tolerate duplicates and skipped observations.
- Disconnect cancellation releases tasks, database sessions, queues, and subscriptions promptly.

## Step 1 — Notifier decision and domain

Evaluate and record the notifier mechanism. **Recommended default for this delivery:** PostgreSQL `LISTEN/NOTIFY` with a database-backed resume query, because event ordering and resume are anchored in the `(updated_at, id)` keyset that PostgreSQL already maintains; missed notifications between listeners are recovered by the resume re-query and by client snapshot reconciliation. If the API is scaled horizontally, each replica runs its own listener and serves only its own connections — no cross-replica bus is needed because every stream re-queries PostgreSQL. Record the chosen mechanism and the replica-topology reasoning here before implementing.

Create `backend/app/domain/read_models/status_event.py`:

```python
@dataclass(frozen=True, slots=True)
class TransactionStatusEvent:
    request_id: UUID
    status: TransactionStatus
    error: str | None
    updated_at: datetime
    transaction_id: UUID  # used only to build the opaque resume cursor
```

Create `backend/app/domain/ports/services/status_notifier.py`:

```python
class StatusNotifier(Protocol):
    async def subscribe(self, user_id: UUID, after: StatusCursor | None) -> AsyncIterator[TransactionStatusEvent]: ...
```

Define the opaque cursor type in the domain as a transparent pair `(updated_at, id)`; base64url encoding is an API concern. Document the client reconciliation rules next to the port (monotonic upsert, regression rejection, skipped-observation tolerance).

## Step 2 — DB and notifier adapter

Create `backend/app/status_notifications/__init__.py` and `backend/app/status_notifications/pg_notifier.py`:

- **Resume query:** on subscribe with a cursor, first run `SELECT … FROM transactions WHERE visible_to(user_id) AND (updated_at, id) > (:u, :i) ORDER BY updated_at ASC, id ASC` (bounded by a page size, looping until caught up) using the Phase 2 cursor index — this replays every missed change.
- **Live tail:** open a dedicated asyncpg connection and `LISTEN transaction_status_changed`; on each notification, re-query PostgreSQL for rows newer than the last emitted cursor (notifications are wakeups, not payloads) — this prevents missed wakeups between the initial query and the wait.
- **Emit side:** repositories that commit status transitions issue `SELECT pg_notify('transaction_status_changed', :user_id)` in the same transaction (add this to the guarded transition methods from Phase 2/3). Notifications never carry event data beyond the routing user id.
- Ensure every status transition updates `updated_at` in the same transaction (already enforced by Phase 2 guarded updates) so resume ordering is consistent.
- Bound every query, use the supporting index, and release the listener connection and sessions promptly on disconnect/cancellation.

## Step 3 — SSE endpoint

Create `backend/app/api/routers/stream.py`:

```python
@router.get("/me/stream")
async def stream_transactions(
    current_user: Annotated[CurrentUser, Depends(bind_current_user)],
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    ...
```

Behavior, per [API_CONTRACT.md](../v2/API_CONTRACT.md):

- Validate authentication before streaming; on failure return the normal JSON `401 AUTHENTICATION_FAILED`.
- Return `200 OK` with exactly `Content-Type: text/event-stream; charset=utf-8`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`.
- Decode `Last-Event-ID` (unpadded base64url of `{"updated_at","id"}`); absent, expired, or unrecognized IDs start a fresh live stream without an HTTP error.
- Emit `event: transaction_status` frames with `id: <opaque cursor>` and `data: {"request_id":"…","status":"…","error":null}`.
- Send `: keep-alive` comments every `SSE_HEARTBEAT_INTERVAL_SECONDS` (default 15s) and a `retry: <SSE_RETRY_MILLISECONDS>` field (≥ 3000) once per connection.
- Disable buffering, compression, and caching in the app and document the trusted-proxy requirements (idle timeouts compatible with the heartbeat; forward `Last-Event-ID`).
- On disconnect/cancellation: cancel the notifier subscription, release sessions/queues/listener. On mid-stream error: close the connection without an error envelope.

Wire the router in `backend/app/main.py`; add the executor/factory in `backend/app/api/dependencies.py` and `backend/app/dependencies.py` following existing patterns.

## Step 4 — UI streaming client

Create `frontend/src/api/streamClient.ts` — native `EventSource` cannot attach a Bearer header, so implement streaming over `fetch`:

- `fetch(`${VITE_API_BASE_URL}/me/stream`, { headers: { Authorization: `Bearer ${token}`, "Last-Event-ID"? } })` and read `response.body` with a `ReadableStream` reader; parse SSE framing (`id:`, `event:`, `data:`, comments) manually with a buffer.
- Never place the JWT in the URL.
- Track the last fully processed event ID; reconnect with it and a bounded retry delay (server `retry:` value, minimum 3000 ms, capped backoff on repeated failures).
- After every initial connection and reconnection, call `GET /me/transactions` and reconcile the snapshot.

Update `frontend/src/pages/WalletPage.tsx`:

- On `transaction_status` events: upsert by `request_id` via `mergeStatus`, tolerate duplicates and skipped states, ignore regressions; render lifecycle status without assuming every intermediate state was observed.
- On `succeeded`: refetch `GET /me/balances` and relevant history.
- On `failed`: clear temporary submission state, refetch authoritative history/balances, display only the safe `error`.
- Show a degraded "live updates unavailable" indicator when disconnected — cached browser state is never presented as authoritative.
- Clean up the stream (abort controller) on unmount and logout.

Update `frontend/src/types/wallet.ts` with the `TransactionStatusEvent` type.

## Step 5 — Smoke check

1. Connect to `GET /me/stream` with a Bearer token (`curl -N -H "Authorization: Bearer …"`), submit a transaction from the UI, and watch `transaction_status` events arrive with plausible payloads and increasing IDs.
2. Disconnect and reconnect with `Last-Event-ID`: the stream resumes or restarts cleanly and the UI reconciles to the authoritative snapshot.
3. Open a second user's stream: it never receives the first user's events; missing/invalid tokens get `401`.
4. Submit and observe: balances refresh after a `succeeded` event; no false success is shown from `202` or `pending`.
5. Observe heartbeats during idle and confirm proxy/browser dev tools show no buffering.

## Migration and rollback

- Phase 4 adds no authoritative status store; the notifier needs no new table. Any notifier-specific schema change would require its own reviewed migration and rollback analysis (not expected).
- Keep `GET /me/transactions` and history queries fully usable when SSE is disabled or degraded.
- If authorization isolation is ever in doubt, disable SSE immediately (feature switch at router registration) without disabling safe authenticated snapshots.
- Roll back frontend and API SSE changes together when event or resume compatibility changes.

## SSE hard stop gate

- [ ] A forced disconnect and reconnect across rapid status changes reaches the correct PostgreSQL snapshot with no regression or cross-user disclosure.
- [ ] The SSE smoke check covers reconnect, skipped states, duplicates, and cross-user isolation without anomalies.
- [ ] Operational telemetry reports connections, disconnects, resume outcomes, notifier lag, and reconciliation failures without high-cardinality metric labels.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app` pass from `backend/`; `yarn lint`, `yarn typecheck`, `yarn build` pass from `frontend/`.
