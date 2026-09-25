# IP-49 - Google Drive Maintenance Operations

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement creation, move, and child enumeration only for bootstrap, audit, repair, discovery, and archive workflows.

## Preconditions

IP-47 and IP-48 VERIFIED.

## Inputs / authoritative references

- `DriveBackend interface`
- `Tree bootstrap/audit requirements`

## Work

1. Implement create_folder and create small text object.
2. Implement move object between canonical parent folders.
3. Implement list_children(parent_id) with pagination.
4. Normalize duplicate-name observations without choosing a winner.
5. Add operation counters/telemetry hooks.
6. Document that list_children is forbidden on normal FETCH_BALL/WAKE_BONE path.

## Files / modules

- `src/tb4/drive/google_backend.py`
- `tests/drive/test_google_backend_maintenance.py`

## Required invariants

- Maintenance enumeration never becomes hidden fallback for exact lookup.
- Moves preserve stable object ID.

## Tests

- Create/move/list pagination.
- Duplicate names returned distinctly.
- Rate-limit/retry surface.
- Move permission error.

## Failure cases

- Pagination silently misses children.
- List helper auto-selects by name.

## Completion evidence required

- Maintenance backend tests pass.

## Handoff state

Bootstrap and TreeHealer can run against production Drive backend.

## Amendment path

`docs/implementation-plan/amendments/IP-49/`

## Evidence path

`docs/implementation-plan/evidence/IP-49/`
