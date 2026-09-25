# IP-21 - Retry and Backoff Helpers

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement bounded deterministic retry behavior so components never invent their own loops.

## Preconditions

IP-14, IP-15, and IP-20 VERIFIED.

## Inputs / authoritative references

- `config/defaults.toml`
- `protocol/config-rules.yaml`

## Work

1. Define RetryPolicy from canonical configuration.
2. Implement bounded attempt iterator with monotonic deadlines.
3. Support Drive confirmation backoff sequence and operation-level attempt ceiling.
4. Classify exhausted retry separately from ambiguous remote result.
5. Inject sleeper/clock in tests to avoid real delays.

## Files / modules

- `src/tb4/core/retry.py`
- `tests/core/test_retry.py`

## Required invariants

- No infinite retry path.
- Retry helper never decides whether a duplicate business operation should be created.

## Tests

- Configured backoff sequence.
- Deadline stops attempts early.
- Attempt ceiling enforced.
- No sleep after success.

## Failure cases

- Zero/negative backoff creates busy loop.
- Retry exhaustion silently reported as ordinary operation failure.

## Completion evidence required

- Retry tests prove bounded behavior and exact attempt counts.

## Handoff state

Remote transaction helpers may use one shared retry implementation.

## Amendment path

`docs/implementation-plan/amendments/IP-21/`

## Evidence path

`docs/implementation-plan/evidence/IP-21/`
