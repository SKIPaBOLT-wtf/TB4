# IP-09 - Canonical Drive Tree Blueprint

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define the deterministic persistent Drive hierarchy and exactly which children are safe to reconstruct.

## Preconditions

IP-03 through IP-08 VERIFIED.

## Inputs / authoritative references

- `Canonical object registry`
- `All protocol state families`

## Work

1. Define TB4 root children START_HERE, PARK_MAP, GENESIS, SETTINGS, DOG_HOUSE, BALL_PARK, STRAY_YARD, and DOG_POUND.
2. Define per-device subtree with DOG_TAG, DOG_SNIFF, DOG_PULSE, KENNEL/WAKE_BONE, PLAYGROUND/FETCH_BALL and STOP_BALL, TOY_BOX, and BONEYARD.
3. Mark every node required, optional, reconstructable, quarantinable, or never-auto-recreated.
4. Define one work thread per device for protocol v1.
5. Define missing-root behavior: stop rather than create a second control plane.
6. Define deterministic initial active filenames for each live logical object.

## Files / modules

- `protocol/tree-blueprint.yaml`
- `docs/DRIVE_TREE.md`
- `tests/protocol/test_tree_blueprint.py`

## Required invariants

- Active control paths are deterministic.
- History and artifacts remain outside live object paths.
- Blueprint contains no private deployment identifiers.

## Tests

- No duplicate sibling names.
- All logical-object references exist in registry.
- Every required node has explicit reconstructability policy.

## Failure cases

- Duplicate live object definition.
- Root incorrectly marked auto-reconstructable.
- Artifact/history path participates in live control state.

## Completion evidence required

- Tree blueprint validator passes.

## Handoff state

Schemas, bootstrap, index, and repair implementation may rely on one canonical hierarchy.

## Amendment path

`docs/implementation-plan/amendments/IP-09/`

## Evidence path

`docs/implementation-plan/evidence/IP-09/`
