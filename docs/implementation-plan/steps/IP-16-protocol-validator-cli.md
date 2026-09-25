# IP-16 - Protocol Validator CLI

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Provide one deterministic command that validates canonical protocol files before runtime code depends on them.

## Preconditions

IP-03 through IP-15 VERIFIED.

## Inputs / authoritative references

- `protocol/objects.yaml`
- `protocol/state-machines.yaml`
- `protocol/tree-blueprint.yaml`
- `protocol/schemas/`
- `protocol/config-rules.yaml`

## Work

1. Create validator entrypoint.
2. Validate YAML/JSON/TOML parseability.
3. Validate cross-references between objects, states, tree nodes, schemas, and config rules.
4. Reject duplicate logical objects and unknown state references.
5. Report concise actionable errors with file/path context.
6. Return nonzero exit code on any validation failure.

## Files / modules

- `tools/validate_protocol.py`
- `src/tb4/core/spec_validation.py`
- `tests/protocol/test_protocol_validator.py`

## Required invariants

- Validator reads canonical specs; it does not silently repair them.
- One validation failure must not hide unrelated failures when safe to collect multiple errors.

## Tests

- Clean repository spec passes.
- Each major malformed fixture fails with targeted message.
- Unknown object/state reference fails.

## Failure cases

- Validator accepts internally inconsistent specs.
- Validator modifies source files.

## Completion evidence required

- CLI exits zero on canonical spec and nonzero on invalid fixtures.

## Handoff state

All later implementation steps can run one protocol validation command as a prerequisite.

## Amendment path

`docs/implementation-plan/amendments/IP-16/`

## Evidence path

`docs/implementation-plan/evidence/IP-16/`
