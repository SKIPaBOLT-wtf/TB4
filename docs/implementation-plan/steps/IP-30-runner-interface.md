# IP-30 - RUNNER Interface

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define a transport-independent local execution API so FETCHER does not embed shell/process mechanics.

## Preconditions

IP-17 and IP-29 VERIFIED.

## Inputs / authoritative references

- `FETCH_BALL schema`
- `TOY_BOX protocol`

## Work

1. Define ExecutionRequest and ExecutionReport models.
2. Support inline command and verified local script path inputs.
3. Define stdout/stderr streaming/capture contract.
4. Define timeout/cancel process-tree termination hooks.
5. Define explicit interpreter selection policy.
6. Define known-side-effect metadata as evidence fields, not inferred promises.

## Files / modules

- `src/tb4/fetcher/runner.py`
- `src/tb4/fetcher/execution_models.py`
- `tests/fetcher/test_runner_contract.py`

## Required invariants

- RUNNER knows nothing about Google Drive lifecycle states.
- FETCHER owns protocol; RUNNER owns local process execution only.

## Tests

- Contract with fake runner.
- Timeout/cancel report shape.
- Invalid interpreter request rejected.

## Failure cases

- RUNNER changes FETCH_BALL state directly.
- Shell command construction conflates transport with execution.

## Completion evidence required

- Runner contract tests pass with deterministic fake implementation.

## Handoff state

Platform-neutral execution implementations may follow one interface.

## Amendment path

`docs/implementation-plan/amendments/IP-30/`

## Evidence path

`docs/implementation-plan/evidence/IP-30/`
