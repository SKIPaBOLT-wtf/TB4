# IP-23 - InMemoryDriveBackend

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Create a deterministic test double capable of simulating remote object identity, rename persistence, and controlled failures.

## Preconditions

IP-22 VERIFIED.

## Inputs / authoritative references

- `DriveBackend contract`

## Work

1. Implement folders/files with stable opaque IDs.
2. Keep file ID stable across rename and move.
3. Implement exact metadata/body access.
4. Implement create and maintenance list operations.
5. Add hooks for delayed visibility, transient errors, ambiguous mutation outcomes, and permission failures.
6. Record operation counters for efficiency tests.

## Files / modules

- `src/tb4/drive/memory_backend.py`
- `tests/drive/test_memory_backend.py`

## Required invariants

- Test backend mimics identity semantics required by TB4 rather than local filesystem path semantics.
- Failure injection is explicit and deterministic.

## Tests

- Stable ID after rename.
- Delayed metadata visibility.
- Ambiguous rename outcome.
- Operation counters.
- Permission/not-found normalization.

## Failure cases

- Failure injection uses randomness.
- Rename produces new object ID.

## Completion evidence required

- Backend contract suite passes against InMemoryDriveBackend.

## Handoff state

Verified transaction logic can be developed without external Google credentials.

## Amendment path

`docs/implementation-plan/amendments/IP-23/`

## Evidence path

`docs/implementation-plan/evidence/IP-23/`
