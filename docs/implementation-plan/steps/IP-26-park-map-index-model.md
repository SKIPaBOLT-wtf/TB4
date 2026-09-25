# IP-26 - PARK_MAP Index Model

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define and implement the canonical map from logical TB4 objects to stable Drive object IDs so normal runtime never has to scan folders.

## Preconditions

IP-09 and IP-22 through IP-25 VERIFIED.

## Inputs / authoritative references

- `protocol/tree-blueprint.yaml`
- `DriveBackend contract`

## Work

1. Define PARK_MAP schema and version fields.
2. Map each canonical root/folder/device/control object to stable Drive IDs.
3. Define device-key naming independent of mutable hostname where possible.
4. Define update rules when a reconstructable child is replaced.
5. Define cache invalidation behavior.
6. Provide exact lookup helpers that fail closed on missing/duplicate logical references.

## Files / modules

- `protocol/schemas/park-map.schema.json`
- `src/tb4/drive/park_map.py`
- `tests/drive/test_park_map.py`

## Required invariants

- PARK_MAP is an optimization/index, not permission to guess when canonical mapping is ambiguous.
- Normal work dispatch uses exact IDs from PARK_MAP.

## Tests

- Round-trip map.
- Missing entry.
- Duplicate logical mapping.
- Schema/version mismatch.
- Update of one replaced child.

## Failure cases

- Fallback silently scans and selects a plausible object.
- Mutable hostname alone becomes permanent identity.

## Completion evidence required

- PARK_MAP tests prove deterministic exact lookup.

## Handoff state

Bootstrap, repair, Watchdog, Fetcher, and COACH can address objects directly.

## Amendment path

`docs/implementation-plan/amendments/IP-26/`

## Evidence path

`docs/implementation-plan/evidence/IP-26/`
