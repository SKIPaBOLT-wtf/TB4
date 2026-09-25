# IP-02 - Canonical Repository Skeleton

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Create the minimal canonical repository layout required before protocol or runtime code is added.

## Preconditions

IP-01 VERIFIED.

## Inputs / authoritative references

- `AGENTS.md`
- `docs/START_HERE.md`
- `docs/execution-contract/`

## Work

1. Create Python package metadata and test configuration.
2. Create canonical top-level paths for protocol, config, source, tests, tools, and decision records.
3. Add package __init__ files where required.
4. Add a minimal import test.
5. Document the skeleton in START_HERE without private deployment data.

## Files / modules

- `pyproject.toml`
- `src/tb4/`
- `protocol/`
- `config/`
- `tests/`
- `tools/`
- `docs/decisions/`

## Required invariants

- Do not invent protocol behavior yet.
- Do not publish private hostnames, addresses, credentials, or deployment identifiers.

## Tests

- Package imports under the configured test environment.
- Required skeleton files and package paths exist.

## Failure cases

- Packaging metadata is invalid.
- Tests cannot import tb4.

## Completion evidence required

- Package import test passes.
- Skeleton paths and navigation docs exist.

## Handoff state

IP-03 may freeze vocabulary using stable repository locations.

## Amendment path

`docs/implementation-plan/amendments/IP-02/`

## Evidence path

`docs/implementation-plan/evidence/IP-02/`
