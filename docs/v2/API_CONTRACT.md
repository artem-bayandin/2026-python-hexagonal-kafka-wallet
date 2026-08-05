# Version 2 HTTP and SSE API contract

## Scope and conventions

This is the canonical external contract for Version 2. It applies the deltas in the [Version 2 design](README.md) to the inherited [Version 1 HTTP contract](../v1/API_CONTRACT.md). Routes remain unversioned while the sample is pre-1.0; a later breaking external change requires an explicit versioned route prefix or an agreed compatibility plan.

- Request and response bodies are JSON and use `snake_case`, except the body of an SSE event, which is JSON carried in an SSE `data` field.
- JSON enum values are lowercase. Transaction types are `deposit`, `withdrawal`, `exchange`, and `transfer`; transaction statuses are `submitted`, `pending`, `in_progress`, `succeeded`, and `failed`; transfer directions are `in` and `out`.
- Currency labels such as `USD` and `USDT` are catalog identifiers and retain their catalog casing.
- UUIDs are lowercase canonical UUID strings.
- Timestamps are UTC RFC 3339 strings. Responses use a `Z` suffix when the offset is zero and may include fractional seconds.
- Monetary amounts are decimal strings, never JSON numbers. Their scale must not exceed the selected currency's `precision`, and values requiring rounding are invalid.
- Authenticated user routes require `Authorization: Bearer <JWT>`.
- Admin routes require `X-Admin-Key` only in `APP_ENV=development`; production deployment is prohibited until a replacement admin authorization mechanism exists.
- HTTP idempotency keys are not part of this contract. Clients must not assume that resubmitting a timed-out POST is deduplicated.

### Breaking changes from Version 1

Version 2 intentionally changes the four wallet-operation POST responses from `201` with a completed transaction to `202` with `request_id`; transaction type, status, and direction enum values from uppercase to lowercase; user balances from `available` to `amount` and `locked`; and administrator transaction reads from descending offset pagination to ascending cursor-based long polling. Clients must migrate these changes as one Version 2 contract and must not mix Version 1 response models with Version 2 routes.

## Shared representations

### List envelope

Non-paginated list endpoints use the shared `DataList` envelope:

```json
{
  "items": []
}
```

Paginated or cursor-based list endpoints extend this envelope with the metadata documented on that endpoint.

### Error envelope

All handled application errors use this envelope:

```json
{
  "code": "INSUFFICIENT_FUNDS",
  "message": "The available balance is insufficient.",
  "details": {}
}
```

`code` is a stable machine-readable error code. `message` is safe for clients. `details` is optional, must be non-sensitive, and is reserved for structured validation metadata. Internal exception text and diagnostic reasons must never be serialized.

### Balance

A balance item represents total funds and the portion currently locked by accepted debit transactions:

```json
{
  "asset": "USDT",
  "amount": "12.50000000",
  "locked": "1.00000000"
}
```

Both values are non-negative decimal strings at the asset's configured precision, and `locked` never exceeds `amount`. Spendable funds are `amount - locked`; the API does not emit a separate spendable field.

### Transaction

```json
{
  "id": "b17e3a12-3395-4b1c-82a5-2e57632fe6b4",
  "request_id": "8527537d-f473-4074-8341-67db94e06e3a",
  "type": "transfer",
  "status": "pending",
  "source_asset": "USDT",
  "dest_asset": "USDT",
  "amount": "1.00000000",
  "error": null,
  "created_at": "2026-08-04T10:00:00Z",
  "updated_at": "2026-08-04T10:00:01Z",
  "direction": "out"
}
```

`id` identifies the transaction row and `request_id` identifies the asynchronous request returned at submission. Both `source_asset` and `dest_asset` keys are emitted; either value may be `null` when it is not meaningful for the transaction type. `error` is `null` unless the transaction has failed, in which case it contains a safe client-facing failure description. `direction` is included only for transfer rows returned to a user and is omitted from admin responses. The API does not emit `completed_at`.

Status normally advances `submitted` → `pending` → `in_progress` → `succeeded` or `failed`. Clients must tolerate skipped observations, repeated observations, and a terminal status appearing before an earlier status was observed. `succeeded` and `failed` are terminal.

## Asynchronous submission

The four wallet-operation POST routes return `202 Accepted` after accepting a request for asynchronous processing:

```json
{
  "request_id": "8527537d-f473-4074-8341-67db94e06e3a"
}
```

A `202 Accepted` response confirms only that the request was durably recorded and assigned a `request_id`; it does not guarantee that the transaction will succeed. The API returns `202` after its bounded immediate publication path finishes: the transaction is normally `pending` after broker acknowledgement, but it may already be `failed` if publication retries were definitively exhausted and the lock was released. Processing may also fail later in the worker. Clients must use the returned `request_id` and observe the authoritative outcome through `GET /me/transactions`, `GET /me/stream`, or `GET /admin/transactions` as appropriate.

Request syntax, authentication, field validation, user lookup, and debit-fund locking happen synchronously. For withdrawal, exchange, and transfer, insufficient spendable funds return `409 INSUFFICIENT_FUNDS`; no transaction is created and no `request_id` is returned. Other synchronous validation failures likewise return an error instead of `202`.

## Authentication

### `POST /auth/otp/request`

Request:

```json
{
  "email": "user@example.com"
}
```

Response: `201 Created`.

```json
{
  "expires_at": "2026-08-04T10:05:00Z",
  "otp": "123456"
}
```

`otp` is present only when `APP_ENV=development` and `ENABLE_DEMO_OTP=true`; it is omitted, not returned as `null`, in every other configuration. The response must never be logged.

### `POST /auth/otp/verify`

Request:

```json
{
  "email": "user@example.com",
  "otp": "123456"
}
```

Response: `200 OK`.

```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "expires_at": "2026-08-04T11:00:00Z"
}
```

### `POST /auth/logout`

Requires a user Bearer token. Response: `204 No Content`. It revokes only the session identified by the current token's `jti`.

## User wallet

All `/me` routes require a user Bearer token and operate only on the authenticated user.

### `GET /me/balances`

Response: `200 OK` with a `DataList` of balance items.

```json
{
  "items": [
    {
      "asset": "USD",
      "amount": "4.0000",
      "locked": "0.0000"
    },
    {
      "asset": "USDT",
      "amount": "12.50000000",
      "locked": "1.00000000"
    }
  ]
}
```

### `POST /me/withdrawals`

Request:

```json
{
  "asset": "USDT",
  "amount": "1.00000000"
}
```

The API locks `amount` in the user's selected wallet before accepting the request. Response: `202 Accepted` with `{ "request_id": "<uuid>" }`.

### `POST /me/exchanges`

Request:

```json
{
  "source_asset": "USDT",
  "destination_asset": "USD",
  "amount": "1.00000000"
}
```

The API locks `amount` in the source wallet before accepting the request. Source and destination assets must differ. Response: `202 Accepted` with `{ "request_id": "<uuid>" }`.

### `POST /me/transfers`

Request:

```json
{
  "email": "recipient@example.com",
  "asset": "USDT",
  "amount": "1.00000000"
}
```

This is a same-currency 1:1 transfer to another user resolved by email. The API resolves the recipient and locks `amount` in the sender's wallet before accepting the request; the worker re-validates the recipient during processing. Response: `202 Accepted` with `{ "request_id": "<uuid>" }`.

### `GET /me/transactions`

Returns transactions involving the authenticated user's wallets. This includes outgoing and incoming transfers; transfer rows include `direction` as `out` or `in`, respectively. Transactions unrelated to the authenticated user are excluded, and all non-transfer rows omit `direction`.

Query parameters:

- `page_number`: optional zero-based integer, default `0`.
- `page_size`: optional integer from `1` through `100`, default `20`.

Rows are ordered by `created_at DESC, id DESC`. Response: `200 OK`.

```json
{
  "total_items": 1,
  "items": [
    {
      "id": "b17e3a12-3395-4b1c-82a5-2e57632fe6b4",
      "request_id": "8527537d-f473-4074-8341-67db94e06e3a",
      "type": "withdrawal",
      "status": "in_progress",
      "source_asset": "USDT",
      "dest_asset": null,
      "amount": "1.00000000",
      "error": null,
      "created_at": "2026-08-04T10:00:00Z",
      "updated_at": "2026-08-04T10:00:02Z"
    }
  ]
}
```

The route is the authoritative user-visible snapshot. A transaction may change between requests, so clients upsert by `id` or `request_id` and replace the stored representation with the newest `updated_at`.

### `GET /me/stream`

Opens a Server-Sent Events stream for status changes to transactions visible through the authenticated user's `GET /me/transactions` query, including incoming transfers. The request requires the normal Bearer token. Browser clients using token authentication must use an authenticated streaming request that can attach the `Authorization` header and implement SSE framing and reconnection; they must not place the JWT in the URL. A successful stream handshake returns `200 OK` with exactly these application-controlled headers:

```http
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-transform
X-Accel-Buffering: no
```

Intermediaries and protocol implementations may add transport headers. The response body is an SSE stream encoded as UTF-8 and must not be response-compressed or buffered.

Each transaction-status event has an opaque event ID, the event name `transaction_status`, and one JSON object in `data`:

```text
id: eyJ1cGRhdGVkX2F0IjoiMjAyNi0wOC0wNFQxMDowMDowMloiLCJpZCI6ImIxN2UzYTEyLTMzOTUtNGIxYy04MmE1LTJlNTc2MzJmZTZiNCJ9
event: transaction_status
data: {"request_id":"8527537d-f473-4074-8341-67db94e06e3a","status":"in_progress","error":null}

```

`error` is `null` unless `status` is `failed`. The server may send SSE comment lines such as `: keep-alive` to keep idle connections open; comments carry no application meaning.

The server may close the stream at any time. Clients reconnect with the standard `Last-Event-ID` header containing the last fully processed event ID and use a retry delay of at least three seconds when the stream does not provide a different SSE `retry` value. Event IDs are opaque to clients.

Delivery across disconnects is resumable but at-least-once: after reconnect, the server resumes after the supplied event ID when possible, and it may replay an already observed event. An absent, expired, or unrecognized event ID starts a fresh live stream and does not produce an HTTP error. Because the stream is a notification channel rather than the source of truth, clients must call `GET /me/transactions` after every initial connection and reconnection, upsert by `request_id`, ignore status regressions, and refetch `GET /me/balances` after observing `succeeded`.

Authentication failure before the stream starts uses the normal JSON error response. Once the `200` SSE response has started, failures are represented by connection closure; the server does not append a JSON error envelope to the stream.

## Reference data

Reference routes are read-only and require either `X-Admin-Key` or `Authorization: Bearer <JWT>`.

### `GET /reference/currencies`

Returns `200 OK` with all currency catalog rows ordered by `label` ascending.

```json
{
  "items": [
    {
      "label": "USD",
      "name": "US Dollar",
      "type": "fiat",
      "precision": 4
    },
    {
      "label": "USDT",
      "name": "Tether USD",
      "type": "crypto",
      "precision": 8
    }
  ]
}
```

`label` is sent as an asset value in wallet-operation requests. `precision` defines accepted amount scale and display formatting.

### `GET /reference/users`

Returns `200 OK` with all registered users ordered by `email` ascending.

```json
{
  "items": [
    {
      "user_id": "b17e3a12-3395-4b1c-82a5-2e57632fe6b4",
      "email": "alice@example.com"
    },
    {
      "user_id": "c28f4b23-4406-5c2d-93b6-3f68743ff7c5",
      "email": "bob@example.com"
    }
  ]
}
```

Wallet-operation requests identify users by `email`, not `user_id`.

## Admin

All `/admin` routes require the admin credential described under conventions.

### `POST /admin/deposits`

Request:

```json
{
  "email": "user@example.com",
  "asset": "USDT",
  "amount": "10.00000000"
}
```

The API resolves the recipient before accepting the request. A deposit is credit-only and does not lock funds. Response: `202 Accepted` with `{ "request_id": "<uuid>" }`.

### `GET /admin/balances`

Returns `200 OK` with a `DataList` of admin-wallet balance items in the shared balance shape. Admin funds are not locked by the four Version 2 operations, so `locked` is `0` for these balances.

```json
{
  "items": [
    {
      "asset": "USD",
      "amount": "1000.0000",
      "locked": "0.0000"
    },
    {
      "asset": "USDT",
      "amount": "1000.00000000",
      "locked": "0.00000000"
    }
  ]
}
```

### `GET /admin/transactions`

Returns transaction snapshots and supports long polling over changes ordered by the keyset `(updated_at ASC, id ASC)`. A status transition updates `updated_at`, so the same transaction may appear in more than one response; clients upsert by `id` or `request_id`.

Query parameters:

- `cursor`: optional opaque cursor returned by the previous response. When omitted, the route returns the first available page immediately.
- `limit`: optional integer from `1` through `100`, default `100`.
- `timeout_seconds`: optional integer from `0` through `30`, default `25`. `0` disables waiting.

The cursor is the unpadded base64url encoding of the UTF-8 JSON object `{"updated_at":"<UTC RFC 3339 timestamp>","id":"<canonical UUID>"}`. The timestamp and UUID identify the last ordered row observed. Clients should treat the encoded value as opaque and send it back unchanged. A malformed cursor returns `422 VALIDATION_ERROR`.

With a cursor, the route selects rows where `(updated_at, id)` is strictly greater than the decoded pair. If rows are available, it returns immediately with at most `limit` items. Otherwise it waits until a row becomes available or `timeout_seconds` elapses. An omitted cursor never waits for an initial page.

Response: `200 OK`.

```json
{
  "items": [
    {
      "id": "b17e3a12-3395-4b1c-82a5-2e57632fe6b4",
      "request_id": "8527537d-f473-4074-8341-67db94e06e3a",
      "type": "deposit",
      "status": "succeeded",
      "source_asset": null,
      "dest_asset": "USDT",
      "amount": "10.00000000",
      "error": null,
      "created_at": "2026-08-04T10:00:00Z",
      "updated_at": "2026-08-04T10:00:03Z"
    }
  ],
  "next_cursor": "eyJ1cGRhdGVkX2F0IjoiMjAyNi0wOC0wNFQxMDowMDowM1oiLCJpZCI6ImIxN2UzYTEyLTMzOTUtNGIxYy04MmE1LTJlNTc2MzJmZTZiNCJ9"
}
```

When items are returned, `next_cursor` encodes the last item. When a long poll times out with no items, the response is `{ "items": [], "next_cursor": "<input cursor>" }`. If an initial request finds no items, `next_cursor` is `null`.

## Diagnostics and health

### `GET /health/live`

Returns `200 OK` when the API process is alive.

```json
{
  "status": "ok"
}
```

### `GET /health/ready`

Returns `200 OK` only when PostgreSQL, the required schema, Kafka, and required topic metadata are usable for Version 2 mutation submission; otherwise it returns `503 Service Unavailable`. Query and SSE degradation may be reported separately by operational telemetry, but the API must not advertise submission readiness while it cannot safely run the bounded publication path. A successful response is:

```json
{
  "status": "ok"
}
```

### `GET /health/authenticated`

Requires a user Bearer token. The API validates the JWT, confirms that its server-side session is active, and loads the current user. Response: `200 OK`.

```json
{
  "status": "ok"
}
```

A missing, malformed, expired, or revoked token returns `401 AUTHENTICATION_FAILED`.

## Errors

Synchronous request failures use the shared error envelope. A transaction that fails after a `202 Accepted` response is not retroactively converted into an HTTP error; its status becomes `failed` and its safe failure description is exposed through transaction reads and SSE.

| Outcome | HTTP status | Error code |
| --- | --- | --- |
| Malformed request, query parameter, cursor, or field validation | 422 | `VALIDATION_ERROR` |
| Missing, malformed, expired, invalid, or revoked token | 401 | `AUTHENTICATION_FAILED` |
| Incorrect OTP | 422 | `OTP_INVALID` |
| Expired OTP | 422 | `OTP_EXPIRED` |
| OTP locked after the maximum failed attempts | 422 | `OTP_LOCKED` |
| Previously consumed OTP | 422 | `OTP_CONSUMED` |
| OTP invalidated by a newer challenge | 422 | `OTP_SUPERSEDED` |
| Invalid admin credential | 403 | `ADMIN_ACCESS_DENIED` |
| Unknown deposit recipient or transfer target | 404 | `USER_NOT_FOUND` |
| Insufficient spendable funds at debit submission | 409 | `INSUFFICIENT_FUNDS` |
| Unsupported asset | 422 | `UNSUPPORTED_ASSET` |
| Invalid amount | 422 | `INVALID_AMOUNT` |
| Invalid precision | 422 | `INVALID_PRECISION` |
| Same source and destination asset | 422 | `SAME_ASSET` |
| Transfer to self | 422 | `TRANSFER_TO_SELF` |
| Readiness dependency unavailable | 503 | `SERVICE_UNAVAILABLE` |
| Unhandled server failure | 500 | `INTERNAL_ERROR` |

Unknown internal error codes are exposed only as `500 INTERNAL_ERROR`. Request-validation failures remain `422 VALIDATION_ERROR`, and uncaught exceptions remain `500 INTERNAL_ERROR`.
