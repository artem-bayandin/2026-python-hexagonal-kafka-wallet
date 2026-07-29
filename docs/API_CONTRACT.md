# HTTP API contract

## Scope and conventions

This is the canonical contract for the HTTP API described by the functional and technical requirements. Routes are unversioned while the sample is pre-1.0. A breaking external contract change requires an explicit `/v2` route prefix or an approved compatibility plan before implementation.

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

```json
{
  "id": "b17e3a12-3395-4b1c-82a5-2e57632fe6b4",
  "type": "EXCHANGE",
  "status": "COMPLETED",
  "created_at": "2026-07-23T10:00:00Z",
  "completed_at": "2026-07-23T10:00:01Z"
}
```

An operation/transaction uses `DEPOSIT`, `EXCHANGE`, or `WITHDRAWAL` for `type`, and `PENDING`, `COMPLETED`, `REJECTED`, or `FAILED` for `status`. `PENDING`, `REJECTED`, and `FAILED` exist only in version 2.

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

Version 2 adds `pending` and `rejected` fields to each balance item. Version 1 must not emit those fields.

### `POST /me/exchanges`

Request:

```json
{
  "source_asset": "USDT",
  "destination_asset": "USD",
  "amount": "1.00"
}
```

Version 1 returns `201 Created` with a completed operation. Version 2 returns `202 Accepted` with a pending operation.

### `POST /me/withdrawals`

Request:

```json
{ "asset": "USDT", "amount": "1.00" }
```

In version 2, the request also contains `source_bucket`, which is `AVAILABLE` or `REJECTED`. The status behavior is the same as exchanges.

### `GET /me/transactions`

### `GET /admin/transactions`

Both routes use cursor pagination:

- `limit`: optional integer from 1 through 100, default 20.
- `cursor`: optional opaque value from the preceding response.
- sort order: `created_at DESC, id DESC`.

Response: `200 OK`.

```json
{
  "items": [],
  "next_cursor": null
}
```

### `GET /me/operations/{operation_id}`

Available in version 2. Returns `200 OK` with an operation representation for the current user, or `404 OPERATION_NOT_FOUND` when the operation does not exist or is not owned by that user.

## Reference

Read-only catalog data. No authentication required.

### `GET /reference/currencies`

Returns `200 OK` and all rows from the `currencies` catalog, ordered by `label` ascending.

```json
{
  "items": [
    { "label": "USD", "name": "US Dollar", "type": "fiat", "precision": 4 },
    { "label": "USDT", "name": "Tether USD", "type": "crypto", "precision": 8 }
  ]
}
```

`label` is the value sent as `asset` in deposit, exchange, and withdrawal requests. `precision` drives amount input validation and formatting in the UI.

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

Version 2 additionally requires `approved`, a boolean mock AML outcome. The route returns `201 Created` in version 1 and `202 Accepted` in version 2.

### `GET /admin/balances`

Returns `200 OK` and the same version-specific balance item shape as `GET /me/balances`.

### `GET /admin/operations/{operation_id}`

Available in version 2. Returns any operation to an authorized development admin; it is not a public route.

## Diagnostics and health

`GET /kafka/messages` and `GET /kafka/messages/{message_id}` exist only in version 2 and only when `APP_ENV=development`. They use the same pagination rules and accept `state`, `command_type`, `operation_id`, and `correlation_id` filters. Disabled diagnostics return `404`.

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

Internally, command and query handlers return `Result[T]`. The API's generic `unwrap_result(result)` helper returns successful data or raises an API-layer exception carrying only the failed result's stable `error_code`. The central API exception handler maps that code to the status and safe envelope below. An unknown code is returned only as `500 INTERNAL_ERROR`; its original value is not exposed.

`unwrap_result` does not choose successful status codes: each route retains the explicit status documented in its section. Request-validation failures remain `422 VALIDATION_ERROR`, and uncaught exceptions remain `500 INTERNAL_ERROR`. `Result.reason`, when present, is internal diagnostic context and must never be serialized into the response. Neither `Result[T]` nor the API-layer exception is part of the HTTP contract.

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
| Inactive user | 403 | `USER_INACTIVE` |
| Missing or inaccessible resource | 404 | `OPERATION_NOT_FOUND` or `MESSAGE_NOT_FOUND` |
| Invalid state or conflicting operation | 409 | Specific conflict code |
| Unsupported asset, invalid precision/amount, or same-asset exchange | 422 | Specific validation code |
| Insufficient funds | 409 | `INSUFFICIENT_FUNDS` |
| Unhandled server failure | 500 | `INTERNAL_ERROR` |

Worker business outcomes are represented as a `200` operation query response with `REJECTED` and a safe reason code. Infrastructure failure is represented as `FAILED`; it is never presented as a business rejection.
