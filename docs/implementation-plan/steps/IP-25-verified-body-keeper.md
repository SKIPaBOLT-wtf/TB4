# IP-25 - Verified BodyKeeper Transaction

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement complete small-body replace with remote readback, schema validation, hash verification, and fence checks.

## Preconditions

IP-19, IP-21, IP-23, and required schemas VERIFIED.

## Inputs / authoritative references

- `Control/object schemas`
- `DriveBackend`
- `FenceGuard`

## Work

1. Validate caller is in a state permitting body mutation.
2. Validate fence before write.
3. Serialize complete body rather than append/prepend mutation.
4. Replace body through backend.
5. Read back authoritative remote body.
6. Validate schema and expected integrity hash.
7. Reconcile ambiguous write outcome before retrying.
8. Return explicit verified/unconfirmed/fence/schema outcomes.

## Files / modules

- `src/tb4/drive/body_keeper.py`
- `tests/drive/test_body_keeper.py`

## Required invariants

- No partial append/prepend protocol.
- Dependent next-state transition occurs only after verified body write.
- Control bodies remain bounded.

## Tests

- Successful verified replace.
- Delayed visibility.
- Ambiguous write that actually applied.
- Hash mismatch.
- Schema-invalid readback.
- Stale fence before and after attempt.
- Retry exhaustion.

## Failure cases

- Helper overwrites newer generation body.
- Schema validation skipped on readback.

## Completion evidence required

- BodyKeeper suite demonstrates verified replace and stale-write prevention.

## Handoff state

Higher-level transactions can safely compose StateWalker and BodyKeeper.

## Amendment path

`docs/implementation-plan/amendments/IP-25/`

## Evidence path

`docs/implementation-plan/evidence/IP-25/`
