# IP-22 Amendment A-001 - Add Explicit Version Conflict Outcome

Date: 2026-09-26

## Problem

DriveBackend mutation methods already accept `expected_version_token`, but the original normalized outcome set had no truthful result for a known compare-and-swap/precondition mismatch.

Mapping a known version mismatch to TRANSIENT_ERROR would imply retry may succeed without reconciliation. Mapping it to AMBIGUOUS would falsely imply the mutation may have happened.

## Decision

Add `CONFLICT` to `BackendOutcome`.

Semantics:

- `CONFLICT` means the requested mutation is known **not** to have been applied because the observed object/version precondition did not match.
- It is safe to inspect/reconcile and decide again.
- It is not equivalent to TRANSIENT_ERROR.
- It is not equivalent to AMBIGUOUS.

## Compatibility impact

Additive within pre-1.0 development. Existing callers matching known outcomes must handle the new explicit outcome.

## Affected future steps

IP-23 and all transaction/backend implementation steps.
