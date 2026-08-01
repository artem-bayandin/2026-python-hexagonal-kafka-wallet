Version 1 (Phases 1–5) is implemented: backend, frontend, PostgreSQL schema, auth, admin wallet, and user wallet flows run locally with the commands below. Automated test suites, CI, and version 2 (Kafka) are not yet complete.

Local version 2:

```sh
docker compose --env-file backend/.env up -d postgres kafka worker
```

The worker must start only after migrations have completed and its readiness check confirms PostgreSQL and Kafka reachability. Shutdown must stop HTTP intake before stopping the worker, allow in-flight database transactions to finish, and leave unprocessed outbox records for retry.

- Emit structured logs with request ID, correlation ID, operation ID, message ID, route, status, and duration. Never log secrets, OTPs, JWTs, or raw credentials.
- Emit metrics for HTTP latency/errors, database connectivity, outbox backlog, publication/consumption failures, operation outcomes, and worker retry age.
- Propagate correlation IDs from HTTP submission through the outbox, Kafka envelope, worker logs, diagnostics records, and operation queries.

- Retain structured logs and metrics sufficient to trace one operation from HTTP submission through Kafka to final balance/history state.
