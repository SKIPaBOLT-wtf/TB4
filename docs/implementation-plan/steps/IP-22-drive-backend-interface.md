# IP-22 - DriveBackend Interface

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define the transport boundary required by TB4 without coupling core protocol logic to Google SDK calls.

## Preconditions

IP-17 through IP-21 VERIFIED.

## Inputs / authoritative references

- `EC-11`
- `Canonical tree and object identity rules`

## Work

1. Define metadata read by stable object ID.
2. Define small text body read and replace.
3. Define rename/move/create folder/create text operations.
4. Define maintenance-only child enumeration.
5. Define explicit result types for success, not found, permission denied, transient error, and ambiguous outcome.
6. Define backend capability flags where APIs differ.

## Files / modules

- `src/tb4/drive/backend.py`
- `src/tb4/drive/errors.py`
- `tests/drive/test_backend_contract.py`

## Required invariants

- Exact object operations are first-class.
- list_children is marked maintenance/discovery, not normal state lookup.
- Backend contains no protocol state decisions.

## Tests

- Abstract contract/interface tests.
- Error normalization expectations.

## Failure cases

- Callers must parse provider-specific exception strings.
- Normal API requires folder listing to address known object.

## Completion evidence required

- Backend contract is documented and testable by multiple implementations.

## Handoff state

An in-memory test backend can implement the same contract before real Drive integration.

## Amendment path

`docs/implementation-plan/amendments/IP-22/`

## Evidence path

`docs/implementation-plan/evidence/IP-22/`
