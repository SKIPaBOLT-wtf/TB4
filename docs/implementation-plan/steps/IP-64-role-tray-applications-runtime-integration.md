# IP-64 - Role Tray Applications and Runtime Integration

> **Status:** Read from `../manifest.yaml`.

## Purpose

Implement independently launched responsive WATCHDOG and FETCHER tray applications using existing runtimes.

## Preconditions

IP-63 VERIFIED.

## Inputs / authoritative references

- `docs/DESKTOP.md`
- Production runtime factories, authorization and bootstrap helpers.

## Work

1. Add configuration, status, bounded history and diagnostic-export windows.
2. Run runtime/auth/check/bootstrap actions in a worker process with a private control pipe.
3. Support cooperative stop/restart, duplicate-launch refusal and no-tray window fallback.
4. Observe existing backend operations without new remote polls or manual state edits.

## Files / modules

- `src/tb4/desktop/app.py`
- `src/tb4/desktop/worker.py`
- `tests/desktop/`

## Required invariants

No blocking UI network work; no replay or forced state reset; peer role unaffected; no public admin endpoint.

## Tests

Offscreen GUI smoke; worker success/failure; stop, restart, EOF, duplicate launch and production import/resource availability.

## Failure cases

Failed startup, missing tray, stalled backend, malformed telemetry and installed legacy service conflict.

## Completion evidence required

GUI and lifecycle tests with explicit platform and credential-free scope.

## Handoff state

Independent desktop applications are ready for platform distribution builds.

## Amendment path

`docs/implementation-plan/amendments/IP-64/`

## Evidence path

`docs/implementation-plan/evidence/IP-64/`
