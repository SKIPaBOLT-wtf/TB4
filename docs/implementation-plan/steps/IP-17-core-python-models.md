# IP-17 - Core Python Models

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Create typed internal models corresponding to canonical protocol identities without adding transport or runtime behavior.

## Preconditions

IP-16 VERIFIED.

## Inputs / authoritative references

- `Canonical protocol specs and schemas`

## Work

1. Define immutable identifiers for logical object root and state.
2. Define OperationId, generation, timestamps, and bounded reason/result enums.
3. Define typed references for device and artifact IDs.
4. Define serialization/deserialization helpers only where canonical encoding is already specified.
5. Keep protocol constants generated from or validated against canonical spec.

## Files / modules

- `src/tb4/core/models.py`
- `src/tb4/core/protocol_names.py`
- `tests/core/test_models.py`

## Required invariants

- Do not create a second independent list of protocol names without validation against specs.
- Models remain transport-agnostic.

## Tests

- Round-trip canonical identifiers.
- Reject invalid generation and malformed IDs.
- Model enum/name coverage matches canonical registry.

## Failure cases

- Code constants drift from protocol YAML.
- Private deployment data appears in model defaults.

## Completion evidence required

- Core model tests pass and canonical name coverage is exact.

## Handoff state

State, fencing, timing, and transport helpers can use shared typed models.

## Amendment path

`docs/implementation-plan/amendments/IP-17/`

## Evidence path

`docs/implementation-plan/evidence/IP-17/`
