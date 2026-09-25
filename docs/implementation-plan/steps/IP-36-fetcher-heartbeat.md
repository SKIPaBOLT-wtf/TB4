# IP-36 - FETCHER Heartbeat

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Publish bounded executor liveness without writing unchanged state excessively.

## Preconditions

IP-13, IP-20, IP-25, and IP-35 VERIFIED.

## Inputs / authoritative references

- `DOG_PULSE schema`
- `Configuration defaults`

## Work

1. Implement active and idle heartbeat cadence.
2. Use local monotonic scheduler and wall-clock protocol timestamp.
3. Increment sequence deterministically.
4. Publish by exact DOG_PULSE object ID.
5. Avoid remote write when cadence has not elapsed.
6. Ensure heartbeat task cannot mutate FETCH_BALL state.

## Files / modules

- `src/tb4/fetcher/heartbeat.py`
- `tests/fetcher/test_heartbeat.py`

## Required invariants

- Heartbeat is liveness evidence, not job success evidence.
- Remote writes remain bounded by configured cadence.

## Tests

- Idle cadence.
- Active cadence.
- Sequence increment.
- Clock anomaly.
- Drive transient failure.

## Failure cases

- Heartbeat busy-loop.
- Heartbeat thread blocks job completion.

## Completion evidence required

- Heartbeat tests show bounded exact-ID writes.

## Handoff state

WATCHDOG can later determine executor freshness from stable heartbeat semantics.

## Amendment path

`docs/implementation-plan/amendments/IP-36/`

## Evidence path

`docs/implementation-plan/evidence/IP-36/`
