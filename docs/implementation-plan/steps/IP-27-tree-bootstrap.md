# IP-27 - GENESIS Tree Bootstrap

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Create a new TB4 persistent tree deterministically from the canonical blueprint without exposing private deployment values.

## Preconditions

IP-09, IP-23, and IP-26 VERIFIED.

## Inputs / authoritative references

- `protocol/tree-blueprint.yaml`
- `PARK_MAP schema`

## Work

1. Implement bootstrap that requires an explicitly selected existing root folder.
2. Create missing canonical static folders and seed control objects in initial READY/CLEAN/SNOOZE states.
3. Create GENESIS metadata recording protocol/schema versions.
4. Build PARK_MAP from actual created stable IDs.
5. Make bootstrap idempotent on an empty or partially created safe tree.
6. Never create a second root automatically.

## Files / modules

- `src/tb4/drive/bootstrap.py`
- `tools/bootstrap_drive.py`
- `tests/drive/test_bootstrap.py`

## Required invariants

- Root identity is explicit input.
- No secrets or host-specific private config in public defaults.
- Creation is idempotent by exact canonical child rules.

## Tests

- Fresh root bootstrap.
- Interrupted bootstrap then resume.
- Second bootstrap no duplicates.
- Missing explicit root rejected.

## Failure cases

- Duplicate control object creation after interrupted run.
- Implicit new root creation.

## Completion evidence required

- Fresh and interrupted bootstrap tests converge to one canonical tree.

## Handoff state

Tree repair may reconcile an existing deployment against the same blueprint.

## Amendment path

`docs/implementation-plan/amendments/IP-27/`

## Evidence path

`docs/implementation-plan/evidence/IP-27/`
