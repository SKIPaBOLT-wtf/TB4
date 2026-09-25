# IP-10 - Common Control Envelope Schema

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define fields shared by reusable live control-object bodies before object-specific schemas are created.

## Preconditions

IP-04 through IP-09 VERIFIED.

## Inputs / authoritative references

- `State machines`
- `Tree blueprint`
- `Fencing requirements`

## Work

1. Define schema_version and protocol_version.
2. Define operation/job ID and generation fields.
3. Define given_at, expires_at, started_at, finished_at, and bounded run_limit_s semantics.
4. Define payload and result integrity hash fields.
5. Define explicit unset semantics for timestamps/exit codes.
6. Define bounded inline text and artifact reference shape.
7. Define canonical serialization expectations for small text control bodies.

## Files / modules

- `protocol/schemas/control-envelope.schema.json`
- `docs/CONTROL_ENVELOPE.md`
- `tests/protocol/test_control_envelope_schema.py`

## Required invariants

- Filename remains authoritative lifecycle state; body does not compete with it.
- Generation and operation identity are mandatory on reusable work channels.

## Tests

- Valid examples accepted.
- Missing required fence fields rejected.
- Oversized bounded fields rejected.
- Invalid timestamp relationships rejected where schema can express them.

## Failure cases

- Null/unset semantics ambiguous.
- Same state encoded independently in body and filename as competing authority.

## Completion evidence required

- Envelope schema tests pass.

## Handoff state

Object-specific body schemas may extend one stable common envelope.

## Amendment path

`docs/implementation-plan/amendments/IP-10/`

## Evidence path

`docs/implementation-plan/evidence/IP-10/`
