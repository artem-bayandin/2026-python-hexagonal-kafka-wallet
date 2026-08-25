# Doc–Code Audit Summary (Phases 1–5)

Audit date: 2026-07-31. **Code is canonical**; docs were updated to match the running version-1 implementation.

## Canonical contracts

| Document | Issue | Resolution |
| --- | --- | --- |
| [API_CONTRACT.md](../API_CONTRACT.md) | Cursor pagination (`limit` / `cursor` / `next_cursor`) | Replaced with offset pagination (`page_number`, `page_size`, `total_items`) |
| [API_CONTRACT.md](../API_CONTRACT.md) | Transaction example included `completed_at`; omitted list fields | Documented `source_asset`, `dest_asset`, `amount`, optional `direction`; v1 omits `completed_at` |
| [API_CONTRACT.md](../API_CONTRACT.md) | Missing `TRANSFER` type | Added to transaction type enum |
| [API_CONTRACT.md](../API_CONTRACT.md) | `unwrap_result` / generic API exception | Renamed to `unwrap_domain_result` / `DomainResultError` |
| [API_CONTRACT.md](../API_CONTRACT.md) | `USER_INACTIVE`; vague error rows | Replaced with `USER_NOT_FOUND`; enumerated v1 codes (`TRANSFER_TO_SELF`, `CREDIT_FAILED`, …) |
| [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md) | No transfer feature | Added §5.5 Transfer; updated actors, history, UI |
| [FUNCTIONAL_REQUIREMENTS.md](../FUNCTIONAL_REQUIREMENTS.md) | Separate History page | History embedded in Wallet view; state-based navigation |
| [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md) | Stale folder tree (`entities/`, monolithic repos) | Updated to `read_models/`, CQRS repos, `executors/`, `db_session.py`, `schemas/shared.py` |
| [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md) | React Router 8 required | `react-router-dom` 7.x installed; v1 UI uses React state |
| [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md) | `unwrap_result` | Renamed to `unwrap_domain_result` |
| [TECHNICAL_REQUIREMENTS.md](../TECHNICAL_REQUIREMENTS.md) | PEP 695 typing | Added policy in §2.1 |

## Phase guides

| Document | Issue | Resolution |
| --- | --- | --- |
| [PHASE_3_WALLET_SCHEMA.md](PHASE_3_WALLET_SCHEMA.md) | Status "not started" | Marked complete (`d377d8c90992`); transfer note updated |
| [PHASE_4_ADMIN_WALLET.md](PHASE_4_ADMIN_WALLET.md) | `data_list.py`, `TypeVar`, two-executor balances, `get_by_normalized_email` | Updated to `shared.py`, PEP 695 pagination, `get_by_email`, historical note |
| [PHASE_5_USER_WALLET.md](PHASE_5_USER_WALLET.md) | Stale formatting, dual-executor balances, verification unchecked | Aligned with code; final verification marked complete |
| [PHASE_2_AUTHENTICATION.md](PHASE_2_AUTHENTICATION.md) | `unwrap_result`, `entities/` architecture | Bulk rename; architecture rules + historical note for slice snippets |
| [PHASE_2A_INSIGHTS.md](PHASE_2A_INSIGHTS.md) | Wallet/tests "not done" | Phases 3–5 marked done; read_models / executors documented |

## Roadmap and ops

| Document | Issue | Resolution |
| --- | --- | --- |
| [IMPLEMENTATION_STEPS.md](../IMPLEMENTATION_STEPS.md) | Steps 1–5, 9–10 unchecked | Marked `[x]`; wording aligned (read models, offset pagination, `unwrap_domain_result`) |
| [README.md](../README.md) | "Pre-implementation" | Updated to implemented v1 sample (not production-ready) |
| [OPERATIONS.md](../OPERATIONS.md) | Commands "not executable" | Updated current status; lifecycle commands valid for v1 |
| [PHASE_5A_TECH_REVIEW.md](PHASE_5A_TECH_REVIEW.md) | Open doc-drift items | Closed doc items; code-only follow-ups noted |
| [LEARN_PY.md](../../LEARN_PY.md) | `unwrap_result` in examples | Renamed to `unwrap_domain_result` |

## Intentionally unchanged (not doc bugs)

- Executor vs yield-handler injection debate ([PHASE_5A_TECH_REVIEW.md](PHASE_5A_TECH_REVIEW.md))
- Rename `app/dependencies.py` composition root
- Phase 2/4 historical slice code blocks still show original `entities/` paths — superseded by historical notes at guide tops
- Automated tests, CI, Kafka (Phases 6–7) — still deferred

## Code-only follow-ups (out of doc scope)

- Remove stale `TypeVar` import in `backend/app/domain/read_models/pagination.py` if present
- Review `cast("T", ...)` in `unwrap_domain_result` if desired
