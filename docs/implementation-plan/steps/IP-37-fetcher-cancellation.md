# IP-37 - FETCHER Cancellation

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement STOP_BALL handling that terminates only the matching active job generation and returns accurate cancellation evidence.

## Preconditions

IP-06, IP-25, IP-31 through IP-36 VERIFIED.

## Inputs / authoritative references

- `STOP_BALL schema/state machine`
- `RUNNER cancellation contract`

## Work

1. Observe exact STOP_BALL object ID.
2. Validate requested job_id/generation against active FETCH_BALL.
3. Acknowledge only matching request.
4. Signal RUNNER/process-tree cancellation.
5. Capture any known partial effects/output.
6. Return FETCH_BALL_CANCELLED through normal RETURNING path.
7. Recycle STOP_BALL only after cancellation acknowledgement/result handling is durable.

## Files / modules

- `src/tb4/fetcher/cancellation.py`
- `tests/fetcher/test_cancellation.py`

## Required invariants

- Stale STOP_BALL cannot cancel newer job.
- Cancellation does not erase known partial work.

## Tests

- Cancel active job.
- Stale job cancel rejected.
- Repeated cancel idempotent.
- Cancel arrives after natural completion.
- Process ignores graceful termination and requires forced kill.

## Failure cases

- Wrong generation terminated.
- STOP_BALL recycled before result durable.

## Completion evidence required

- Cancellation suite proves generation safety and process termination.

## Handoff state

Fetcher service can support explicit cancellation while preserving protocol evidence.

## Amendment path

`docs/implementation-plan/amendments/IP-37/`

## Evidence path

`docs/implementation-plan/evidence/IP-37/`
