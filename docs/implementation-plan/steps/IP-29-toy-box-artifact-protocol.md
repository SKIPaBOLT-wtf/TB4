# IP-29 - TOY_BOX Artifact Protocol

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define bounded artifact transport for scripts and large results so TB4 never depends on giant inline command strings.

## Preconditions

IP-10 through IP-13 and IP-26 VERIFIED.

## Inputs / authoritative references

- `EC-17`
- `EC-18`

## Work

1. Define artifact metadata schema: artifact_id, kind, size, sha256, interpreter hint, created_at, expiry/retention.
2. Define request script artifact and result artifact types.
3. Define deterministic references from FETCH_BALL body to TOY_BOX objects.
4. Define upload-complete verification rule before a FETCH_BALL may be TOSSed.
5. Define local filename/suffix derivation without trusting remote path strings.
6. Define cleanup and retention ownership.

## Files / modules

- `protocol/schemas/artifact.schema.json`
- `docs/TOY_BOX.md`
- `tests/protocol/test_artifact_schema.py`

## Required invariants

- Artifact content is never trusted before size/hash verification.
- Remote artifact name never becomes an arbitrary local path.
- Secrets are not stored merely because artifact transport exists.

## Tests

- Script artifact fixture.
- Large result fixture.
- Hash mismatch.
- Oversize rejection.
- Unsafe filename metadata rejection.

## Failure cases

- FETCH_BALL can reference partially uploaded artifact.
- Artifact path traversal possible.

## Completion evidence required

- Artifact schema/security tests pass.

## Handoff state

Runner and artifact spool can consume verified TOY_BOX references.

## Amendment path

`docs/implementation-plan/amendments/IP-29/`

## Evidence path

`docs/implementation-plan/evidence/IP-29/`
