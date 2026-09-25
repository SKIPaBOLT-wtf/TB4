# IP-39 - WATCHDOG Scheduler

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement one low-overhead event/timer scheduler that dispatches helpers without busy loops.

## Preconditions

IP-20, IP-21, and core schemas VERIFIED.

## Inputs / authoritative references

- `WATCHDOG timing defaults`
- `EC-21`

## Work

1. Define scheduled task abstraction with next_due monotonic time.
2. Support idle and active DOG modes.
3. Schedule heartbeat, known-device probes, stray scans, audits, retention, and active-job watches independently.
4. Apply deterministic per-task/device phase offsets.
5. Allow event-triggered immediate dispatch without resetting unrelated schedules.
6. Expose scheduler metrics for tests.

## Files / modules

- `src/tb4/watchdog/scheduler.py`
- `tests/watchdog/test_scheduler.py`

## Required invariants

- No busy polling.
- One slow helper cannot silently destroy timing state for others.
- Phase offsets are deterministic.

## Tests

- Task ordering.
- Phase offsets.
- Idle/active cadence switch.
- Event wakeup.
- Clock jump resilience via monotonic clock.

## Failure cases

- All devices fire simultaneously after restart.
- Exception in one helper stops scheduler.

## Completion evidence required

- Scheduler tests show bounded wakeups and independent task cadence.

## Handoff state

Network, wake, audit, and retention helpers can plug into one scheduler.

## Amendment path

`docs/implementation-plan/amendments/IP-39/`

## Evidence path

`docs/implementation-plan/evidence/IP-39/`
