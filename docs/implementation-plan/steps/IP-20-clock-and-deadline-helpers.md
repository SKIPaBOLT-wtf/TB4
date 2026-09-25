# IP-20 - Clock and Deadline Helpers

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Centralize UTC epoch timestamps, monotonic duration measurement, expiry, lease, and deadline decisions.

## Preconditions

IP-14 and IP-17 VERIFIED.

## Inputs / authoritative references

- `Configuration defaults`
- `Control envelope timing fields`

## Work

1. Expose wall-clock UTC epoch provider for protocol timestamps.
2. Expose monotonic clock for local durations and sleeps.
3. Implement accept-expiry, run-deadline, lease-expiry, and stale-age helpers.
4. Permit fake clock injection for tests.
5. Define bounded clock-skew sanity check without silently correcting remote clocks.

## Files / modules

- `src/tb4/core/clock.py`
- `src/tb4/core/deadlines.py`
- `tests/core/test_clock_deadlines.py`

## Required invariants

- Never use wall-clock subtraction for local sleep duration when monotonic time is available.
- Expired work is never executed because a target woke late.

## Tests

- Boundary at exact expiry.
- Fake clock forward progression.
- Backward wall-clock anomaly handling.
- Run limit and lease examples.

## Failure cases

- Negative ages treated as healthy indefinitely.
- Wall-clock jump causes unbounded wait.

## Completion evidence required

- Deterministic fake-clock tests pass.

## Handoff state

Retry, Watchdog, Fetcher, and wake logic can share one timing implementation.

## Amendment path

`docs/implementation-plan/amendments/IP-20/`

## Evidence path

`docs/implementation-plan/evidence/IP-20/`
