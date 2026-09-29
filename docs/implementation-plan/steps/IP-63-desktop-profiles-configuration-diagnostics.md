# IP-63 - Desktop Profiles Configuration and Diagnostics

> **Status:** Read from `../manifest.yaml`.

## Purpose

Implement private role-isolated profiles, safe configuration changes and bounded diagnostics.

## Preconditions

IP-62 VERIFIED.

## Inputs / authoritative references

- `docs/DESKTOP.md`
- Existing production validators and backend interface.

## Work

1. Add private role-specific paths and OS-held process locks.
2. Implement TOML validation, optimistic concurrency, backups and atomic save.
3. Implement allowlisted telemetry and stale/unknown state handling without remote polling.

## Files / modules

- `src/tb4/desktop/profile.py`
- `src/tb4/desktop/telemetry.py`
- `tests/desktop/`

## Required invariants

Role isolation; no private content in diagnostics; unchanged protocol; no blind overwrite.

## Tests

Concurrent saves, locked profiles, malformed input, rollback, role isolation, redaction and stale status.

## Failure cases

Invalid configuration, concurrent writers, stale or malformed observations and filesystem errors.

## Completion evidence required

Exact unit/integration test results and reviewed mutation/privacy boundaries.

## Handoff state

Tray applications can rely on tested local support.

## Amendment path

`docs/implementation-plan/amendments/IP-63/`

## Evidence path

`docs/implementation-plan/evidence/IP-63/`
