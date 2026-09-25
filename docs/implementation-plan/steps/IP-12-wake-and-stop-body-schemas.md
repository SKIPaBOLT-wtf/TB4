# IP-12 - WAKE_BONE and STOP_BALL Body Schemas

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define compact request/result bodies for wake/bootstrap and cancellation channels.

## Preconditions

IP-05, IP-06, and IP-10 VERIFIED.

## Inputs / authoritative references

- `WAKE_BONE state machine`
- `STOP_BALL state machine`
- `Common control envelope`

## Work

1. Define wake target identity reference, expiry, reason code, and requested executor-start behavior.
2. Define wake result fields for host seen, executor started, and failure reason.
3. Define STOP_BALL target job_id/generation fields.
4. Define cancellation acknowledgement metadata.
5. Define field requirements by lifecycle phase.
6. Add positive and negative fixtures.

## Files / modules

- `protocol/schemas/wake-bone.schema.json`
- `protocol/schemas/stop-ball.schema.json`
- `protocol/examples/wake-bone/`
- `protocol/examples/stop-ball/`
- `tests/protocol/test_wake_stop_schemas.py`

## Required invariants

- No credentials or SSH secrets in wake bodies.
- STOP_BALL must always identify one exact job generation.

## Tests

- Expired/invalid wake request fixtures rejected.
- Stale/missing generation cancellation rejected.
- Valid terminal wake failure remains target-local.

## Failure cases

- Wake body embeds secret material.
- Cancellation request can match by name only.

## Completion evidence required

- WAKE_BONE and STOP_BALL schema suites pass.

## Handoff state

Wake and cancellation runtime code can later validate bodies before acting.

## Amendment path

`docs/implementation-plan/amendments/IP-12/`

## Evidence path

`docs/implementation-plan/evidence/IP-12/`
