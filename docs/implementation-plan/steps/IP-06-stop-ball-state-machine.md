# IP-06 - STOP_BALL State Machine

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define cancellation as a separate deterministic control object tied to exactly one active job generation.

## Preconditions

IP-03 VERIFIED and IP-04 VERIFIED.

## Inputs / authoritative references

- `FETCH_BALL state machine`
- `EC-16`

## Work

1. Define READY -> REQUESTED -> ACKNOWLEDGED -> READY.
2. Require matching job_id and generation before acknowledgement.
3. Define behavior when no matching FETCH_BALL is active.
4. Define idempotent repeated cancellation.
5. Define how FETCH_BALL becomes CANCELLED and reports any partial effects.

## Files / modules

- `protocol/state-machines.yaml`
- `docs/STOP_BALL.md`
- `tests/protocol/test_stop_ball_spec.py`

## Required invariants

- STOP_BALL must never cancel a newer generation.
- Cancellation result remains on FETCH_BALL rather than creating a second result channel.

## Tests

- Matching cancellation accepted.
- Stale generation rejected.
- Repeated cancellation is idempotent.

## Failure cases

- Cancellation targets wrong generation.
- STOP_BALL itself becomes stuck without recovery semantics.

## Completion evidence required

- STOP_BALL transition graph and generation constraints validate.

## Handoff state

Fetcher cancellation may later be implemented mechanically from this state machine.

## Amendment path

`docs/implementation-plan/amendments/IP-06/`

## Evidence path

`docs/implementation-plan/evidence/IP-06/`
