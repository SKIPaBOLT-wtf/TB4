# IP-45 - WATCHDOG Health and DOG_SHIT Handling

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement global control-plane blocking only for faults that make WATCHDOG operation unreliable.

## Preconditions

IP-07, IP-24, IP-25, IP-28, IP-39 VERIFIED.

## Inputs / authoritative references

- `WATCHDOG control states`
- `EC-22`

## Work

1. Define runtime fault classifier mapping exceptions/events to local, transport-recoverable, protocol-blocking, or global-blocking scope.
2. Implement DOG_SHIT_CLEAN -> BLOCKING verified transition with compact current-error body.
3. Stop accepting new control work while BLOCKING.
4. Allow read-only diagnostics/repair helpers needed to recover.
5. Record review acknowledgement then clear only after underlying invariant validates again.
6. Keep one current blocking error rather than append-only giant log.

## Files / modules

- `src/tb4/watchdog/health.py`
- `tests/watchdog/test_health.py`

## Required invariants

- DOG_SHIT never becomes a generic command-error log.
- Blocking state cannot clear merely because time passed.

## Tests

- Drive root inaccessible.
- PARK_MAP irreducibly ambiguous.
- Ordinary WOL failure nonblocking.
- One target GONE nonblocking.
- Repair then reviewed/clean flow.

## Failure cases

- Global blocker ignored.
- Target-local issue causes park-wide shutdown.

## Completion evidence required

- Fault-scope matrix and recovery tests pass.

## Handoff state

WATCHDOG service can fail closed without overreacting to ordinary target/job faults.

## Amendment path

`docs/implementation-plan/amendments/IP-45/`

## Evidence path

`docs/implementation-plan/evidence/IP-45/`
