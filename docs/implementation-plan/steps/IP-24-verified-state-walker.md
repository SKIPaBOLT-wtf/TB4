# IP-24 - Verified StateWalker Rename Transaction

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement the mandatory rename -> remote-confirm state transition helper with fencing and bounded retries.

## Preconditions

IP-18, IP-19, IP-21, and IP-23 VERIFIED.

## Inputs / authoritative references

- `EC-12`
- `EC-13`
- `State machine validator`
- `DriveBackend`

## Work

1. Read exact object metadata by stable ID.
2. Validate expected current state and actor transition.
3. Validate optional fence.
4. Perform rename to target state.
5. Read remote metadata until target state is confirmed or policy exhausts.
6. If outcome was ambiguous, reconcile same object ID before any repeat mutation.
7. Return NEW_SUCCESS, IDEMPOTENT_SUCCESS, STATE_CONFLICT, STALE_FENCE, or UNCONFIRMED/FAILURE without inventing a new logical operation.

## Files / modules

- `src/tb4/drive/state_walker.py`
- `tests/drive/test_state_walker.py`

## Required invariants

- No dependent body write occurs inside StateWalker.
- No folder listing used on normal path.
- Retries act on the same object ID.

## Tests

- Immediate success.
- Delayed visibility.
- Ambiguous rename that actually succeeded.
- True transient failure then success.
- Wrong expected state.
- Stale generation.
- Retry exhaustion.

## Failure cases

- Helper renames twice after first rename actually succeeded but was delayed.
- Unknown state treated as retryable.

## Completion evidence required

- StateWalker suite proves exact-ID reconciliation and bounded retry.

## Handoff state

All later state mutations must route through StateWalker.

## Amendment path

`docs/implementation-plan/amendments/IP-24/`

## Evidence path

`docs/implementation-plan/evidence/IP-24/`
