# IP-07 - WATCHDOG Control States

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define WATCHDOG operating and blocking states without conflating target or job errors with global control-plane failure.

## Preconditions

IP-03 VERIFIED.

## Inputs / authoritative references

- `EC-22`
- `Canonical vocabulary registry`

## Work

1. Define DOG_SNOOZE and the canonical active/awake counterpart.
2. Define DOG_SHIT_CLEAN, DOG_SHIT_BLOCKING, and DOG_SHIT_REVIEWED lifecycle.
3. Define exactly which fault classes may set DOG_SHIT_BLOCKING.
4. Define which component owns review and clear transitions.
5. Define DOG_PULSE semantics separately from DOG mode.
6. Define how a restart reconstructs watchdog mode safely.

## Files / modules

- `protocol/state-machines.yaml`
- `docs/WATCHDOG_STATES.md`
- `tests/protocol/test_watchdog_states.py`

## Required invariants

- DOG_SHIT is reserved for WATCHDOG/control-plane inability to work reliably.
- Target offline, job failure, WOL failure, or one FETCH_BALL_GONE are not DOG_SHIT by themselves.

## Tests

- Blocking/nonblocking classification examples.
- Illegal direct clear from unresolved blocking state rejected.
- Restart semantics represented.

## Failure cases

- Local target error can globally block the park.
- Global integrity failure can be ignored or auto-cleared without review.

## Completion evidence required

- WATCHDOG state definitions and scope tests pass.

## Handoff state

Runtime watchdog health logic may rely on precise global-fault semantics.

## Amendment path

`docs/implementation-plan/amendments/IP-07/`

## Evidence path

`docs/implementation-plan/evidence/IP-07/`
