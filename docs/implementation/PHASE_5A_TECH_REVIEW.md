# Phase 4a — Review

Scope: while implementing phases, some questions were left open. In current phase we should review, discuss, possibly improve, and document our findings and decisions regarding the topics listed below.

## Repositories

- verify functions names, if these are accurate or not about what's happening inside;
- verify sql commands;
- verify it all together with commands and queries where these repositories are used, try to find a better solution;
- verify functions to duplicates
- UserCommandRepositoryImpl.get_by_normalized_email with no lock?

## Domain entities

- are they needed? might they have another fields?
- mappers from domain <-> db, domain <-> api

## Dependencies

Two files mess me around:
- `backend/app/dependencies.py`
- `backend/app/api/dependencies.py`

Review both. Review function namings. In the end of the day it should look easy to read and understand. Maybe split into more files.

Dependencies files should be reviewed together with api routes/etc, where deps are used, to find a better solution.

## Routers

Review how executors and handlers are created for routers. It should all go aligned with a single scheme. Executors and Handlers might be the same entity, as well as handling/executing.

## Other

- require-admin-key + require-jwt = composition of two
