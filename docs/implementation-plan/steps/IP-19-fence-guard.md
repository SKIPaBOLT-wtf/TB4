# IP-19 - FenceGuard

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Prevent stale workers or delayed processes from mutating a reused logical channel belonging to a newer job.

## Preconditions

IP-17 VERIFIED.

## Inputs / authoritative references

- `EC-16`
- `Control envelope schema`

## Work

1. Define fence token as stable object ID plus operation/job ID plus generation plus expected state where needed.
2. Implement fence comparison as pure helper.
3. Define stale, mismatch, and valid outcomes.
4. Require generation to increase monotonically according to channel reset rules.
5. Provide helper for safe pre-write fence assertion.

## Files / modules

- `src/tb4/core/fencing.py`
- `tests/core/test_fencing.py`

## Required invariants

- Old worker can never write because filename happens to match a familiar state.
- Fence validation has no transport side effects.

## Tests

- Matching fence passes.
- Old generation rejected.
- Wrong job ID rejected.
- Object ID mismatch rejected.
- New state with stale generation rejected.

## Failure cases

- Any missing fence component silently treated as wildcard.

## Completion evidence required

- Stale-generation and stale-job tests prove rejection.

## Handoff state

Verified transaction helpers can enforce ownership before writes.

## Amendment path

`docs/implementation-plan/amendments/IP-19/`

## Evidence path

`docs/implementation-plan/evidence/IP-19/`
