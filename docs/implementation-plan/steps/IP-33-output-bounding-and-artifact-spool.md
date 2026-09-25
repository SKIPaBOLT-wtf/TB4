# IP-33 - Output Bounding and Artifact Spool

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Keep live control objects small while preserving complete large output when required.

## Preconditions

IP-29 through IP-32 VERIFIED.

## Inputs / authoritative references

- `Result size contract`
- `TOY_BOX schema`

## Work

1. Implement bounded tail buffers for stdout/stderr.
2. Define inline threshold from configuration.
3. Spool complete oversized output into a result artifact.
4. Hash and verify result artifact before referencing it.
5. Populate FETCH_BALL result with bounded tails plus artifact ID/hash.
6. Support no-artifact path for small results.

## Files / modules

- `src/tb4/fetcher/artifact_spool.py`
- `tests/fetcher/test_artifact_spool.py`

## Required invariants

- Live control body never grows unbounded.
- Artifact creation failure is reported explicitly and does not fabricate successful full-output preservation.

## Tests

- Small output inline.
- Large stdout artifact.
- Large stderr artifact.
- Mixed output.
- Artifact write/hash failure.

## Failure cases

- Large output causes memory blowup.
- Result claims full artifact when upload failed.

## Completion evidence required

- Configured threshold behavior and artifact integrity tests pass.

## Handoff state

Result classification and return pipeline can use bounded evidence.

## Amendment path

`docs/implementation-plan/amendments/IP-33/`

## Evidence path

`docs/implementation-plan/evidence/IP-33/`
