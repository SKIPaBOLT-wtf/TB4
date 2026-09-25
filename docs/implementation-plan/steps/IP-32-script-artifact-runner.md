# IP-32 - Script Artifact Runner

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Execute large/structured commands from verified artifacts as local temporary scripts, eliminating the old giant SSH command-line failure mode.

## Preconditions

IP-29 through IP-31 VERIFIED.

## Inputs / authoritative references

- `TOY_BOX protocol`
- `RUNNER contract`

## Work

1. Materialize verified artifact bytes to a restricted temporary directory.
2. Verify hash again after local materialization.
3. Choose allowed interpreter from explicit policy.
4. Execute script file directly rather than reconstructing its content into a command line.
5. Capture ExecutionReport.
6. Remove or preserve temporary script according to debug/cleanup policy without leaking secrets.

## Files / modules

- `src/tb4/fetcher/artifact_runner.py`
- `tests/fetcher/test_artifact_runner.py`

## Required invariants

- Artifact hash verified before execution.
- Remote-supplied path never controls local destination.
- Large scripts are never embedded into SSH bootstrap command.

## Tests

- Large multiline script succeeds.
- Hash mismatch refuses execution.
- Interpreter mismatch.
- Timeout/cancel.
- Temporary-file cleanup.

## Failure cases

- Script executed before full download/hash check.
- Temporary path traversal.

## Completion evidence required

- Multiline/large-script tests pass without command-line reconstruction.

## Handoff state

FETCHER may choose inline or artifact execution based on validated request form.

## Amendment path

`docs/implementation-plan/amendments/IP-32/`

## Evidence path

`docs/implementation-plan/evidence/IP-32/`
