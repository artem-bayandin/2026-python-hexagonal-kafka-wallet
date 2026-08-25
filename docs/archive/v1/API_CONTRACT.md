# HTTP API contract

## Scope and conventions

This is the canonical contract for the HTTP API described by the functional and technical requirements.

- Bodies are JSON and use `snake_case`.
- UUIDs are canonical strings. Timestamps are UTC RFC 3339 strings.
- Monetary amounts are decimal strings, never JSON numbers.
- Authenticated user routes use `Authorization: Bearer <JWT>`.
- Admin routes require `X-Admin-Key` only in `APP_ENV=development`; production deployment is prohibited until a replacement authorization mechanism exists.
- HTTP idempotency keys are not part of the baseline API. They are reserved for the roadmap's final optional hardening phase and no endpoint requires `Idempotency-Key` unless that phase is explicitly started.

## Shared representations

```json
{
  "asset": "USDT",
  "amount": "12.50000000"
}
```

`asset` is one of `USDT` or `USD`. Amount scale must not exceed the asset scale.
The API rejects values requiring rounding.

Non-paginated list endpoints use a shared **`DataList`** envelope:

```json
{
  "items": [ ... ]
}
```

Paginated list endpoints extend this shape with offset fields (for example `total_items` on `GET /admin/transactions`).

Transaction list items:

```json
{
  "id": "b17e3a12-3395-4b1c-82a5-2e57632fe6b4",
  "type": "EXCHANGE",
  "status": "COMPLETED",
  "source_asset": "USDT",
  "dest_asset": "USD",
  "amount": "1.00000000",
  "created_at": "2026-07-23T10:00:00Z"
}
```

`GET /me/transactions` may also include `direction` (`IN` or `OUT`) on transfer rows. Admin transaction lists omit `direction`. The API does not emit `completed_at`.

An operation/transaction uses `DEPOSIT`, `EXCHANGE`, `WITHDRAWAL`, or `TRANSFER` for `type`, and `COMPLETED` for `status`.

## Authentication

### `POST /auth/otp/request`

Request:

```json
{ "email": "user@example.com" }
```

Response: `201 Created`.

```json
{
  "expires_at": "2026-07-23T10:05:00Z",
  "otp": "123456"
}
```

`otp` is present only when `APP_ENV=development` and `ENABLE_DEMO_OTP=true`; it must be omitted, not returned as `null`, in every other configuration. The response must never be logged.

### `POST /auth/otp/verify`

Request:

```json
{ "email": "user@example.com", "otp": "123456" }
```

Response: `200 OK`.

```json
{
  "access_token": "jwt",
  "token_type": "bearer",
  "expires_at": "2026-07-23T11:00:00Z"
}
```

### `POST /auth/logout`

Requires a user Bearer token. Response: `204 No Content`. It revokes only the session identified by the current token's `jti`.

### `GET /health/authenticated`

Requires a user Bearer token. The API validates the JWT, confirms that its server-side session is active, and loads the current user.

Response: `200 OK`.

```json
{ "status": "ok" }
```

A missing, malformed, expired, or revoked token returns `401 AUTHENTICATION_FAILED` using the standard error envelope.

## User wallet

### `GET /me/balances`

Response: `200 OK`.

```json
{
  "items": [
    { "asset": "USDT", "available": "12.50000000" },
    { "asset": "USD", "available": "4.0000" }
  ]
}
```

### `POST /me/exchanges`

Request:

```json
{
  "source_asset": "USDT",
  "destination_asset": "USD",
  "amount": "1.00"
}
```

Returns `201 Created` with a completed operation.

### `POST /me/withdrawals`

Request:

```json
{ "asset": "USDT", "amount": "1.00" }
```

Returns `201 Created` with a completed operation.

### `POST /me/transfers`

Request:

```json
{
  "email": "recipient@example.com",
  "asset": "USDT",
  "amount": "1.00000000"
}
```

Same-currency 1:1 transfer to another user; recipient resolved by email. Returns `201 Created`.

### `GET /me/transactions`

### `GET /admin/transactions`

Both routes use offset pagination:

- `page_number`: optional zero-based integer, default 0.
- `page_size`: optional integer from 1 through 100, default 20.
- sort order: `created_at DESC, id DESC`.

Response: `200 OK`.

```json
{
  "total_items": 0,
  "items": []
}
```

## Reference

Read-only catalog data. Both routes require `X-Admin-Key` or `Authorization: Bearer`.

### `GET /reference/currencies`

Requires `X-Admin-Key` or `Authorization: Bearer`. Returns `200 OK` and all rows from the `currencies` catalog, ordered by `label` ascending.

```json
{
  "items": [
    { "label": "USD", "name": "US Dollar", "type": "fiat", "precision": 4 },
    { "label": "USDT", "name": "Tether USD", "type": "crypto", "precision": 8 }
  ]
}
```

`label` is the value sent as `asset` in deposit, exchange, withdrawal, and transfer requests. `precision` drives amount input validation and formatting in the UI.

### `GET /reference/users`

Requires `X-Admin-Key` or `Authorization: Bearer`. Returns `200 OK` and all registered users, ordered by `email` ascending.

```json
{
  "items": [
    { "user_id": "b17e3a12-3395-4b1c-82a5-2e57632fe6b4", "email": "alice@example.com" },
    { "user_id": "c28f4b23-4406-5c2d-93b6-3f68743ff7c5", "email": "bob@example.com" }
  ]
}
```

The UI displays and selects by **email only** (ignores `user_id` for now). Deposit and transfer requests send `email`, not `user_id`.

## Admin

### `POST /admin/deposits`

Request:

```json
{
  "email": "user@example.com",
  "asset": "USDT",
  "amount": "10.00000000"
}
```

Returns `201 Created`.

### `GET /admin/balances`

Returns `200 OK` and the same balance item shape as `GET /me/balances`.

## Diagnostics and health

`GET /health/live` returns `200` when the process is alive. `GET /health/ready` returns `200` only when required dependencies are reachable, otherwise `503`. Both return:

```json
{ "status": "ok" }
```

## Errors

All handled application errors use this envelope:

```json
{
  "code": "INSUFFICIENT_FUNDS",
  "message": "The available balance is insufficient for this withdrawal.",
  "details": {}
}
```

`message` is safe for clients. `details` is optional, must be non-sensitive, and is intended only for structured validation metadata.

Internally, command and query handlers return `Result[T]`. The API's generic `unwrap_domain_result(result)` helper returns successful data or raises `DomainResultError` carrying only the failed result's stable `error_code`. The central API exception handler maps that code to the status and safe envelope below. An unknown code is returned only as `500 INTERNAL_ERROR`; its original value is not exposed.

`unwrap_domain_result` does not choose successful status codes: each route retains the explicit status documented in its section. Request-validation failures remain `422 VALIDATION_ERROR`, and uncaught exceptions remain `500 INTERNAL_ERROR`. `Result.reason`, when present, is internal diagnostic context and must never be serialized into the response. Neither `Result[T]` nor `DomainResultError` is part of the HTTP contract.

| Outcome | HTTP status | Error code |
| --- | --- | --- |
| Malformed request or field validation | 422 | `VALIDATION_ERROR` |
| Missing, malformed, expired, invalid, or revoked token | 401 | `AUTHENTICATION_FAILED` |
| Incorrect OTP | 422 | `OTP_INVALID` |
| Expired OTP | 422 | `OTP_EXPIRED` |
| OTP locked after the maximum failed attempts | 422 | `OTP_LOCKED` |
| Previously consumed OTP | 422 | `OTP_CONSUMED` |
| OTP invalidated by a newer challenge | 422 | `OTP_SUPERSEDED` |
| Invalid admin credential | 403 | `ADMIN_ACCESS_DENIED` |
| Unknown user (deposit recipient or transfer target) | 404 | `USER_NOT_FOUND` |
| Insufficient funds or failed credit | 409 | `INSUFFICIENT_FUNDS` or `CREDIT_FAILED` |
| Unsupported asset | 422 | `UNSUPPORTED_ASSET` |
| Invalid amount | 422 | `INVALID_AMOUNT` |
| Invalid precision | 422 | `INVALID_PRECISION` |
| Same source and destination asset (exchange) | 422 | `SAME_ASSET` |
| Transfer to self | 422 | `TRANSFER_TO_SELF` |
| Unhandled server failure | 500 | `INTERNAL_ERROR` |
