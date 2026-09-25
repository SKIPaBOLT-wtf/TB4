# IP-28 - Tree Audit, Repair, and DOG_POUND Quarantine

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement conservative reconciliation for missing, duplicate, unknown, or corrupt persistent objects.

## Preconditions

IP-27 VERIFIED.

## Inputs / authoritative references

- `EC-24`
- `EC-25`
- `Tree blueprint`
- `PARK_MAP`

## Work

1. Enumerate folders only in explicit audit/repair mode.
2. Compare actual children with canonical blueprint and PARK_MAP.
3. Recreate only children marked safely reconstructable.
4. Preserve canonical stable-ID object when a duplicate is found.
5. Move ambiguous duplicates/corrupt extras to DOG_POUND with bounded metadata.
6. Update PARK_MAP only after verified replacement/adoption.
7. Escalate irreducible root/index ambiguity to blocking fault rather than guessing.

## Files / modules

- `src/tb4/drive/tree_healer.py`
- `src/tb4/drive/tree_audit.py`
- `tests/drive/test_tree_healer.py`

## Required invariants

- Repair never silently deletes ambiguous data.
- Normal runtime remains scan-free.
- Missing root is blocking, not auto-recreated.

## Tests

- Missing child repair.
- Duplicate control object quarantine.
- Unknown child handling.
- Corrupt canonical object.
- Ambiguous index mapping blocks repair.

## Failure cases

- Repair chooses duplicate by name/mtime guess.
- DOG_POUND move loses provenance.

## Completion evidence required

- Failure-injected tree tests recover or block exactly as specified.

## Handoff state

Watchdog can safely invoke periodic audits and repairs.

## Amendment path

`docs/implementation-plan/amendments/IP-28/`

## Evidence path

`docs/implementation-plan/evidence/IP-28/`
