# Documentation index

## Authority and status

This documentation describes an **implemented version-1 sample** (synchronous wallet). It is not authorization to deploy a real custodial-wallet service. The application must not be called production-ready until automated checks, deployment configuration, and operational controls described here pass review.

## Repository layout

```
project-root/
├── backend/     # Python API
├── frontend/    # React UI
└── docs/        # Canonical requirements and phase guides
```

## Reading order

| Document | Authority | Purpose |
| --- | --- | --- |
| [Functional requirements](FUNCTIONAL_REQUIREMENTS.md) | Canonical product contract | Defines user-visible behavior, version differences, and non-goals. |
| [Technical requirements](TECHNICAL_REQUIREMENTS.md) | Canonical architecture contract | Defines stack, dependency policy, boundaries, security controls, and reliability rules. |
| [API contract](API_CONTRACT.md) | Canonical HTTP contract | Defines payloads, HTTP outcomes, errors, pagination, and compatibility. |
| [Configuration](CONFIGURATION.md) | Canonical configuration contract | Defines profiles, environment variables, ports, and secret policy. |
| [Operations](OPERATIONS.md) | Canonical operating contract | Defines health checks, lifecycle commands, observability, backup, release, rollback, and incident expectations. |
| [Implementation steps](IMPLEMENTATION_STEPS.md) | Canonical delivery plan | Defines the build sequence and its completion criteria. |
| [Phase guides](implementation/) | Runnable delivery guides | Step-by-step terminal commands for each implementation phase. |

`WALLET_SAMPLE_PROPOSAL_0.md` is retained only as an archived decision record. It is non-authoritative and must not be updated to introduce or change requirements. Its aligned with code of the Version_1 copy is in `WALLET_SAMPLE_PROPOSAL_ALIGNED_V1_.md`, which is also non-authoritative and must not be updated to introduce or change requirements. 

## Version boundaries

| Area | Version 1 | Version 2 |
| --- | --- | --- |
| Wallet mutations | Execute synchronously and return completed results. | Submit an operation and return `202 Accepted`; the worker later completes, rejects, or fails it. |
| Balances | Single amount per wallet row. | Pending/rejected amounts per currency (strategy TBD). |
| Infrastructure | PostgreSQL. | PostgreSQL, Kafka, outbox relay, and worker. |
| Wallet feedback | Immediate result or error. | Pending operation ID and polling feedback. |
| Kafka diagnostics | Not present. | Development-only diagnostics, disabled outside development. |

## Change rules

- Change behavior only in the canonical document for that concern.
- Update API and configuration documentation with any implementation change that affects clients or operators.
- Record intentionally incompatible API or data changes before implementing them; version the API or migration path rather than silently changing it.
