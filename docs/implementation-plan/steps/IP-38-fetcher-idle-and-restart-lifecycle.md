# IP-38 - FETCHER Idle and Restart Lifecycle

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Allow FETCHER to exit after configured idle time while recovering safely after restart.

## Preconditions

IP-35 through IP-37 VERIFIED.

## Inputs / authoritative references

- `Fetcher timing defaults`
- `FETCH_BALL fencing semantics`

## Work

1. Define idle as no active job, no pending TOSS, and no cancellation handling.
2. Start idle timer only after pipeline is fully READY.
3. Prevent exit while RUNNER child exists.
4. On startup inspect exact current FETCH_BALL/STOP_BALL states.
5. If CHEW belongs to a dead previous process, do not fabricate result; expose state for WATCHDOG recovery.
6. Publish initial heartbeat before accepting new work where required.

## Files / modules

- `src/tb4/fetcher/service.py`
- `src/tb4/fetcher/idle_manager.py`
- `tests/fetcher/test_service_lifecycle.py`

## Required invariants

- Ten-minute-style idle policy is configurable, not hardcoded.
- Service restart never assumes a prior CHEW completed.

## Tests

- Idle exit.
- No exit during active child.
- Startup READY.
- Startup stale CHEW.
- Startup pending TOSS.
- Restart with stale STOP_BALL.

## Failure cases

- Fetcher exits mid-job.
- Restart re-executes old CHEW blindly.

## Completion evidence required

- Lifecycle tests prove safe idle shutdown and restart inspection.

## Handoff state

WATCHDOG bootstrap may start a complete self-managing FETCHER service.

## Amendment path

`docs/implementation-plan/amendments/IP-38/`

## Evidence path

`docs/implementation-plan/evidence/IP-38/`
