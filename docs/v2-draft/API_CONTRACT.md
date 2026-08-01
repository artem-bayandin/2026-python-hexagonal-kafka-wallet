This is the canonical contract for the HTTP API described by the functional and technical requirements. Routes are unversioned while the sample is pre-1.0. A breaking external contract change requires an explicit `/v2` route prefix or an approved compatibility plan before implementation.

An operation/transaction uses `DEPOSIT`, `EXCHANGE`, `WITHDRAWAL`, or `TRANSFER` for `type`, and `PENDING`, `COMPLETED`, `REJECTED`, or `FAILED` for `status`. `PENDING`, `REJECTED`, and `FAILED` exist only in version 2.

Version 2 adds `pending` and `rejected` fields to each balance item. Version 1 must not emit those fields.

Version 1 returns `201 Created` with a completed operation. Version 2 returns `202 Accepted` with a pending operation.

In version 2, the request also contains `source_bucket`, which is `AVAILABLE` or `REJECTED`. The status behavior is the same as exchanges.

### `GET /me/operations/{operation_id}`

Available in version 2. Returns `200 OK` with an operation representation for the current user, or `404 OPERATION_NOT_FOUND` when the operation does not exist or is not owned by that user.

Version 2 additionally requires `approved`, a boolean mock AML outcome. The route returns `201 Created` in version 1 and `202 Accepted` in version 2.

### `GET /admin/operations/{operation_id}`

Available in version 2. Returns any operation to an authorized development admin; it is not a public route.

`GET /kafka/messages` and `GET /kafka/messages/{message_id}` exist only in version 2 and only when `APP_ENV=development`. They use the same pagination rules and accept `state`, `command_type`, `operation_id`, and `correlation_id` filters. Disabled diagnostics return `404`.

| Missing or inaccessible resource (version 2) | 404 | `OPERATION_NOT_FOUND` or `MESSAGE_NOT_FOUND` |

Worker business outcomes are represented as a `200` operation query response with `REJECTED` and a safe reason code. Infrastructure failure is represented as `FAILED`; it is never presented as a business rejection.
